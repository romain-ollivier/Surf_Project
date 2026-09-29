WITH conditions AS (

    SELECT *
    FROM {{ ref('int_surf_conditions') }}

),

scoring_parameters AS (

    SELECT *
    FROM {{ ref('surf_spot_scoring_parameters') }}

),

base AS (

    SELECT
        c.*,

        -- Tide preference
        spc.tide_preference,

        -- Swell period parameters
        p.period_optimal_min_s,
        p.period_optimal_max_s,
        p.period_very_good_min_s,
        p.period_very_good_max_s,

        -- Wind speed parameters
        p.wind_optimal_max_kmh,
        p.wind_very_good_max_kmh,
        p.wind_good_max_kmh,
        p.wind_poor_max_kmh,

        -- Swell height parameters
        p.swell_height_low_max_m,
        p.swell_height_good_min_m,
        p.swell_height_optimal_min_m,
        p.swell_height_optimal_max_m,
        p.swell_height_large_min_m,

        -- Wave size parameters
        p.size_too_small_max_m,
        p.size_ideal_min_m,
        p.size_ideal_max_m,
        p.size_large_min_m,
        p.size_extreme_min_m

    FROM conditions AS c

    LEFT JOIN scoring_parameters AS p
        ON c.spot_id = p.spot_id

    LEFT JOIN {{ ref('surf_spot_characteristics') }} AS spc
        ON c.spot_id = spc.spot_id
),

wind_speed_scored AS (

    SELECT
        *,

        CASE

            WHEN wind_speed_kmh IS NULL
                THEN NULL

            WHEN wind_speed_kmh <= wind_optimal_max_kmh
                THEN 100.0

            WHEN wind_speed_kmh <= wind_very_good_max_kmh
                THEN
                    100.0
                    - (
                        (wind_speed_kmh - wind_optimal_max_kmh)
                        / NULLIF(
                            wind_very_good_max_kmh
                            - wind_optimal_max_kmh,
                            0
                        )
                    ) * 15.0

            WHEN wind_speed_kmh <= wind_good_max_kmh
                THEN
                    85.0
                    - (
                        (wind_speed_kmh - wind_very_good_max_kmh)
                        / NULLIF(
                            wind_good_max_kmh
                            - wind_very_good_max_kmh,
                            0
                        )
                    ) * 20.0

            WHEN wind_speed_kmh <= wind_poor_max_kmh
                THEN
                    65.0
                    - (
                        (wind_speed_kmh - wind_good_max_kmh)
                        / NULLIF(
                            wind_poor_max_kmh
                            - wind_good_max_kmh,
                            0
                        )
                    ) * 40.0

            ELSE 0.0

        END AS wind_speed_index

    FROM base
),

wind_direction_matches AS (

    SELECT
        w.*,

        (
            SELECT MAX(
                CASE

                    WHEN p.preference_level = 'PRIMARY'
                        AND (
                            (
                                p.direction_min_deg <= p.direction_max_deg
                                AND w.wind_direction_deg
                                    BETWEEN p.direction_min_deg
                                    AND p.direction_max_deg
                            )
                            OR
                            (
                                p.direction_min_deg > p.direction_max_deg
                                AND (
                                    w.wind_direction_deg >= p.direction_min_deg
                                    OR w.wind_direction_deg <= p.direction_max_deg
                                )
                            )
                        )
                        THEN 100.0

                    WHEN p.preference_level = 'SECONDARY'
                        AND (
                            (
                                p.direction_min_deg <= p.direction_max_deg
                                AND w.wind_direction_deg
                                    BETWEEN p.direction_min_deg
                                    AND p.direction_max_deg
                            )
                            OR
                            (
                                p.direction_min_deg > p.direction_max_deg
                                AND (
                                    w.wind_direction_deg >= p.direction_min_deg
                                    OR w.wind_direction_deg <= p.direction_max_deg
                                )
                            )
                        )
                        THEN 85.0

                    ELSE NULL

                END
            )

            FROM {{ ref('surf_spot_direction_preferences') }} AS p

            WHERE p.spot_id = w.spot_id
              AND p.direction_type = 'WIND'

        ) AS preferred_wind_direction_score

    FROM wind_speed_scored AS w
),

wind_direction_scored AS (

    SELECT
        *,

        CASE

            WHEN wind_direction_deg IS NULL
                THEN NULL

            WHEN preferred_wind_direction_score IS NOT NULL
                THEN preferred_wind_direction_score

            ELSE 40.0

        END AS wind_direction_index

    FROM wind_direction_matches
),

wind_scored AS (

    SELECT
        *,

        (
            wind_direction_index * 0.60
            + wind_speed_index * 0.40
        ) AS wind_index

    FROM wind_direction_scored
),

swell_direction_matches AS (

    SELECT
        w.*,

        (
            SELECT MAX(

                CASE

                    -- PRIMARY : direction dans la fenêtre
                    WHEN p.preference_level = 'PRIMARY'
                        AND (
                            (
                                p.direction_min_deg <= p.direction_max_deg
                                AND w.swell_direction_deg
                                    BETWEEN p.direction_min_deg
                                    AND p.direction_max_deg
                            )
                            OR
                            (
                                p.direction_min_deg > p.direction_max_deg
                                AND (
                                    w.swell_direction_deg >= p.direction_min_deg
                                    OR w.swell_direction_deg <= p.direction_max_deg
                                )
                            )
                        )
                        THEN 100.0

                    -- SECONDARY : direction dans la fenêtre
                    WHEN p.preference_level = 'SECONDARY'
                        AND (
                            (
                                p.direction_min_deg <= p.direction_max_deg
                                AND w.swell_direction_deg
                                    BETWEEN p.direction_min_deg
                                    AND p.direction_max_deg
                            )
                            OR
                            (
                                p.direction_min_deg > p.direction_max_deg
                                AND (
                                    w.swell_direction_deg >= p.direction_min_deg
                                    OR w.swell_direction_deg <= p.direction_max_deg
                                )
                            )
                        )
                        THEN 75.0

                    -- PRIMARY : direction proche de la fenêtre
                    WHEN p.preference_level = 'PRIMARY'
                        THEN
                            GREATEST(
                                0.0,
                                100.0
                                - (
                                    CASE

                                        WHEN p.direction_min_deg
                                             <= p.direction_max_deg
                                            THEN
                                                CASE
                                                    WHEN w.swell_direction_deg
                                                         < p.direction_min_deg
                                                        THEN
                                                            p.direction_min_deg
                                                            - w.swell_direction_deg

                                                    WHEN w.swell_direction_deg
                                                         > p.direction_max_deg
                                                        THEN
                                                            w.swell_direction_deg
                                                            - p.direction_max_deg

                                                    ELSE 0.0
                                                END

                                        ELSE
                                            LEAST(
                                                ABS(
                                                    w.swell_direction_deg
                                                    - p.direction_max_deg
                                                ),
                                                ABS(
                                                    w.swell_direction_deg
                                                    - p.direction_min_deg
                                                )
                                            )

                                    END
                                ) / 22.5 * 100.0
                            )

                    -- SECONDARY : direction proche de la fenêtre
                    WHEN p.preference_level = 'SECONDARY'
                        THEN
                            GREATEST(
                                0.0,
                                75.0
                                - (
                                    CASE

                                        WHEN p.direction_min_deg
                                             <= p.direction_max_deg
                                            THEN
                                                CASE
                                                    WHEN w.swell_direction_deg
                                                         < p.direction_min_deg
                                                        THEN
                                                            p.direction_min_deg
                                                            - w.swell_direction_deg

                                                    WHEN w.swell_direction_deg
                                                         > p.direction_max_deg
                                                        THEN
                                                            w.swell_direction_deg
                                                            - p.direction_max_deg

                                                    ELSE 0.0
                                                END

                                        ELSE
                                            LEAST(
                                                ABS(
                                                    w.swell_direction_deg
                                                    - p.direction_max_deg
                                                ),
                                                ABS(
                                                    w.swell_direction_deg
                                                    - p.direction_min_deg
                                                )
                                            )

                                    END
                                ) / 22.5 * 75.0
                            )

                    ELSE NULL

                END

            )

            FROM {{ ref('surf_spot_direction_preferences') }} AS p

            WHERE p.spot_id = w.spot_id
              AND p.direction_type = 'SWELL'

        ) AS preferred_swell_direction_score

    FROM wind_scored AS w
),

swell_direction_scored AS (

    SELECT
        *,

        CASE

            WHEN swell_direction_deg IS NULL
                THEN NULL

            WHEN preferred_swell_direction_score IS NOT NULL
                THEN preferred_swell_direction_score

            ELSE 0.0

        END AS calculated_swell_direction_index

    FROM swell_direction_matches
),

swell_height_scored AS (

    SELECT
        *,

        CASE

            WHEN swell_height_m IS NULL
                THEN NULL

            -- Very low
            WHEN swell_height_m <= swell_height_low_max_m
                THEN 20.0

            -- Low → Good
            WHEN swell_height_m <= swell_height_good_min_m
                THEN
                    20.0
                    + (
                        (
                            swell_height_m
                            - swell_height_low_max_m
                        )
                        / NULLIF(
                            swell_height_good_min_m
                            - swell_height_low_max_m,
                            0
                        )
                    ) * 50.0

            -- Good → Optimal
            WHEN swell_height_m <= swell_height_optimal_min_m
                THEN
                    70.0
                    + (
                        (
                            swell_height_m
                            - swell_height_good_min_m
                        )
                        / NULLIF(
                            swell_height_optimal_min_m
                            - swell_height_good_min_m,
                            0
                        )
                    ) * 30.0

            -- Optimal range
            WHEN swell_height_m <= swell_height_optimal_max_m
                THEN 100.0

            -- Optimal → Large
            WHEN swell_height_m <= swell_height_large_min_m
                THEN
                    100.0
                    - (
                        (
                            swell_height_m
                            - swell_height_optimal_max_m
                        )
                        / NULLIF(
                            swell_height_large_min_m
                            - swell_height_optimal_max_m,
                            0
                        )
                    ) * 60.0

            -- Very large
            ELSE 0.0

        END AS swell_height_index

    FROM swell_direction_scored
),

swell_period_scored AS (

    SELECT
        sh.*,

        CASE
            WHEN sh.swell_period_s IS NULL
                THEN NULL

            WHEN sh.swell_period_s < sp.period_p25_s
                THEN 20.0

            WHEN sh.swell_period_s < sp.period_median_s
                THEN
                    20.0
                    + (
                        (sh.swell_period_s - sp.period_p25_s)
                        / NULLIF(
                            sp.period_median_s - sp.period_p25_s,
                            0
                        )
                    ) * 50.0

            WHEN sh.swell_period_s < sp.period_p75_s
                THEN
                    70.0
                    + (
                        (sh.swell_period_s - sp.period_median_s)
                        / NULLIF(
                            sp.period_p75_s - sp.period_median_s,
                            0
                        )
                    ) * 30.0

            WHEN sh.swell_period_s < sp.period_p90_s
                THEN
                    100.0
                    - (
                        (sh.swell_period_s - sp.period_p75_s)
                        / NULLIF(
                            sp.period_p90_s - sp.period_p75_s,
                            0
                        )
                    ) * 20.0

            ELSE 100.0

        END AS swell_period_index

    FROM swell_height_scored AS sh

    INNER JOIN scoring_parameters AS sp
        ON sh.spot_id = sp.spot_id

),

size_scored AS (

    SELECT
        *,

        CASE

            WHEN wave_height_m IS NULL
                THEN NULL

            -- Too small
            WHEN wave_height_m <= size_too_small_max_m
                THEN 20.0

            -- Too small → Ideal
            WHEN wave_height_m <= size_ideal_min_m
                THEN
                    20.0
                    + (
                        (
                            wave_height_m
                            - size_too_small_max_m
                        )
                        / NULLIF(
                            size_ideal_min_m
                            - size_too_small_max_m,
                            0
                        )
                    ) * 80.0

            -- Ideal range
            WHEN wave_height_m <= size_ideal_max_m
                THEN 100.0

            -- Ideal → Large
            WHEN wave_height_m <= size_large_min_m
                THEN
                    100.0
                    - (
                        (
                            wave_height_m
                            - size_ideal_max_m
                        )
                        / NULLIF(
                            size_large_min_m
                            - size_ideal_max_m,
                            0
                        )
                    ) * 40.0

            -- Large → Extreme
            WHEN wave_height_m <= size_extreme_min_m
                THEN
                    60.0
                    - (
                        (
                            wave_height_m
                            - size_large_min_m
                        )
                        / NULLIF(
                            size_extreme_min_m
                            - size_large_min_m,
                            0
                        )
                    ) * 60.0

            -- Extreme
            ELSE 0.0

        END AS size_index

    FROM swell_period_scored
),

swell_scored AS (

    SELECT
        *,

        (
            size_index * 0.50
            + swell_period_index * 0.20
            + calculated_swell_direction_index * 0.30
        ) AS swell_index

    FROM size_scored
),

tide_percentiles AS (

    SELECT
        spot_id,

        PERCENTILE_CONT(0.75) WITHIN GROUP (
            ORDER BY water_level_m
        ) AS p75_water_level

    FROM swell_scored

    WHERE water_level_m IS NOT NULL

    GROUP BY spot_id
),

tide_scored AS (

    SELECT
        s.*,

        CASE

            WHEN s.water_level_m IS NULL
                THEN NULL

            -- Spot compatible avec tous les niveaux de marée
            WHEN s.tide_preference = 'ALL'
                THEN 100.0

            -- Spot préférant une marée basse / intermédiaire
            WHEN s.tide_preference = 'LOW_MID'
                AND s.water_level_m <= p.p75_water_level
                THEN 100.0

            -- Marée haute pour un spot LOW_MID
            WHEN s.tide_preference = 'LOW_MID'
                AND s.water_level_m > p.p75_water_level
                THEN 40.0

            ELSE 40.0

        END AS tide_index

    FROM swell_scored AS s

    LEFT JOIN tide_percentiles AS p
        ON s.spot_id = p.spot_id
),

surf_scored AS (

    SELECT
        *,

        (
            swell_index * 0.50
            + wind_index * 0.275
            + tide_index * 0.225
        ) AS surf_index

    FROM tide_scored
),

surf_classified AS (

    SELECT
        *,

        CASE

            WHEN surf_index < 20
                THEN 'VERY_POOR'

            WHEN surf_index < 40
                THEN 'POOR'

            WHEN surf_index < 60
                THEN 'GOOD'

            WHEN surf_index < 80
                THEN 'VERY_GOOD'

            ELSE 'OPTIMAL'

        END AS surf_quality_band

    FROM surf_scored
)

SELECT
    *

FROM surf_classified

WHERE observation_time >= CURRENT_DATE
  AND observation_time < CURRENT_DATE + INTERVAL '7 days'

  -- Required components for Surf Index
  AND wind_speed_index IS NOT NULL
  AND wind_direction_index IS NOT NULL
  AND swell_index IS NOT NULL
  AND tide_index IS NOT NULL