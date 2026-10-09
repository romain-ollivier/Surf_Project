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
        p.period_too_short_s,
        p.period_optimal_min_s,
        p.period_optimal_max_s,
        p.period_too_long_s,
        p.period_very_good_min_s,
        p.period_very_good_max_s,

        -- Wind speed parameters
        p.wind_optimal_max_kmh,
        p.wind_very_good_max_kmh,
        p.wind_good_max_kmh,
        p.wind_poor_max_kmh,
        p.wind_extreme_kmh,

        -- Swell height parameters
        p.swell_height_low_max_m,
        p.swell_height_good_min_m,
        p.swell_height_optimal_min_m,
        p.swell_height_optimal_max_m,
        p.swell_height_large_min_m,
        p.swell_height_extreme_min_m,

        -- Wave size parameters
        p.size_too_small_max_m,
        p.size_ideal_min_m,
        p.size_ideal_max_m,
        p.size_large_min_m,
        p.size_extreme_min_m,

        -- Spot-specific tide preference curve
        p.tide_low_score,
        p.tide_low_mid_score,
        p.tide_mid_score,
        p.tide_high_mid_score,
        p.tide_high_score

    FROM conditions AS c

    LEFT JOIN scoring_parameters AS p
        ON c.spot_id = p.spot_id

    LEFT JOIN {{ ref('surf_spot_characteristics') }} AS spc
        ON c.spot_id = spc.spot_id
),

direction_inputs AS (

    SELECT
        spot_id,
        observation_time,
        'SWELL' AS direction_type,
        swell_direction_deg AS direction_deg
    FROM base

    UNION ALL

    SELECT
        spot_id,
        observation_time,
        'WIND' AS direction_type,
        wind_direction_deg AS direction_deg
    FROM base
),

direction_preferences AS (

    SELECT
        spot_id,
        direction_type,
        MAX(direction_min_deg) FILTER (
            WHERE preference_level = 'PRIMARY'
        ) AS primary_min_deg,
        MAX(direction_max_deg) FILTER (
            WHERE preference_level = 'PRIMARY'
        ) AS primary_max_deg

    FROM {{ ref('surf_spot_direction_preferences') }}

    GROUP BY
        spot_id,
        direction_type
),

normalized_direction_preferences AS (

    SELECT
        spot_id,
        direction_type,
        MOD(MOD(primary_min_deg::numeric, 360) + 360, 360)
            AS primary_start_deg,
        MOD(MOD(primary_max_deg::numeric, 360) + 360, 360)
            AS primary_end_deg,
        MOD(
            MOD(primary_max_deg::numeric, 360)
            - MOD(primary_min_deg::numeric, 360)
            + 360,
            360
        ) AS primary_arc_deg

    FROM direction_preferences
),

normalized_direction_inputs AS (

    SELECT
        spot_id,
        observation_time,
        direction_type,
        direction_deg,
        CASE
            WHEN direction_deg IS NULL THEN NULL
            ELSE MOD(MOD(direction_deg::numeric, 360) + 360, 360)
        END AS normalized_direction_deg

    FROM direction_inputs
),

direction_positions AS (

    SELECT
        i.spot_id,
        i.observation_time,
        i.direction_type,
        i.direction_deg,
        i.normalized_direction_deg,
        p.primary_start_deg,
        p.primary_end_deg,
        p.primary_arc_deg,
        MOD(
            i.normalized_direction_deg - p.primary_start_deg + 360,
            360
        ) AS primary_position_deg

    FROM normalized_direction_inputs AS i

    INNER JOIN normalized_direction_preferences AS p
        ON i.spot_id = p.spot_id
        AND i.direction_type = p.direction_type
),

secondary_direction_windows AS (

    SELECT
        spot_id,
        direction_type,
        MOD(MOD(direction_min_deg::numeric, 360) + 360, 360)
            AS secondary_start_deg,
        MOD(MOD(direction_max_deg::numeric, 360) + 360, 360)
            AS secondary_end_deg

    FROM {{ ref('surf_spot_direction_preferences') }}

    WHERE preference_level = 'SECONDARY'
),

secondary_direction_positions AS (

    SELECT
        p.spot_id,
        p.observation_time,
        p.direction_type,
        p.direction_deg,
        p.normalized_direction_deg,
        p.primary_start_deg,
        p.primary_end_deg,
        s.secondary_start_deg,
        s.secondary_end_deg,
        MOD(
            s.secondary_end_deg - s.secondary_start_deg + 360,
            360
        ) AS secondary_arc_deg,
        MOD(
            p.normalized_direction_deg - s.secondary_start_deg + 360,
            360
        ) AS secondary_position_deg,
        CASE
            WHEN s.secondary_end_deg = p.primary_start_deg
                THEN 'BEFORE_PRIMARY'
            WHEN s.secondary_start_deg = p.primary_end_deg
                THEN 'AFTER_PRIMARY'
        END AS secondary_side

    FROM direction_positions AS p

    INNER JOIN secondary_direction_windows AS s
        ON p.spot_id = s.spot_id
        AND p.direction_type = s.direction_type
),

primary_direction_scores AS (

    SELECT
        spot_id,
        observation_time,
        direction_type,
        direction_deg,

        CASE
            WHEN direction_deg IS NULL
                OR primary_arc_deg = 0
                OR primary_position_deg > primary_arc_deg
                THEN NULL

            ELSE GREATEST(
                65.0,
                LEAST(
                    100.0,
                    100.0
                    - 35.0
                    * ABS(primary_position_deg - primary_arc_deg / 2.0)
                    / NULLIF(primary_arc_deg / 2.0, 0)
                )
            )
        END AS direction_score

    FROM direction_positions
),

secondary_direction_scores AS (

    SELECT
        spot_id,
        observation_time,
        direction_type,
        direction_deg,

        CASE
            WHEN direction_deg IS NULL
                OR secondary_side IS NULL
                OR secondary_arc_deg = 0
                OR secondary_position_deg > secondary_arc_deg
                THEN NULL

            WHEN secondary_side = 'BEFORE_PRIMARY'
                THEN GREATEST(
                    45.0,
                    LEAST(
                        65.0,
                        45.0
                        + 20.0 * secondary_position_deg
                        / NULLIF(secondary_arc_deg, 0)
                    )
                )

            ELSE GREATEST(
                45.0,
                LEAST(
                    65.0,
                    65.0
                    - 20.0 * secondary_position_deg
                    / NULLIF(secondary_arc_deg, 0)
                )
            )
        END AS direction_score

    FROM secondary_direction_positions
),

outside_secondary_direction_scores AS (

    SELECT
        spot_id,
        observation_time,
        direction_type,
        direction_deg,

        CASE
            WHEN direction_deg IS NULL OR secondary_side IS NULL
                THEN NULL

            ELSE GREATEST(
                0.0,
                45.0 * (
                    1.0
                    - LEAST(
                        ABS(
                            normalized_direction_deg
                            - CASE
                                WHEN secondary_side = 'BEFORE_PRIMARY'
                                    THEN secondary_start_deg
                                ELSE secondary_end_deg
                            END
                        ),
                        360.0 - ABS(
                            normalized_direction_deg
                            - CASE
                                WHEN secondary_side = 'BEFORE_PRIMARY'
                                    THEN secondary_start_deg
                                ELSE secondary_end_deg
                            END
                        )
                    ) / 180.0
                )
            )
        END AS direction_score

    FROM secondary_direction_positions
),

direction_score_candidates AS (

    SELECT * FROM primary_direction_scores

    UNION ALL

    SELECT * FROM secondary_direction_scores

    UNION ALL

    SELECT * FROM outside_secondary_direction_scores
),

direction_scores_by_type AS (

    SELECT
        spot_id,
        observation_time,
        direction_type,
        CASE
            WHEN MAX(direction_deg) IS NULL THEN NULL
            ELSE GREATEST(0.0, LEAST(100.0, MAX(direction_score)))
        END AS direction_score

    FROM direction_score_candidates

    GROUP BY
        spot_id,
        observation_time,
        direction_type
),

direction_scores AS (

    SELECT
        spot_id,
        observation_time,
        MAX(direction_score) FILTER (
            WHERE direction_type = 'WIND'
        ) AS preferred_wind_direction_score,
        MAX(direction_score) FILTER (
            WHERE direction_type = 'SWELL'
        ) AS preferred_swell_direction_score

    FROM direction_scores_by_type

    GROUP BY
        spot_id,
        observation_time
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
                    ) * 20.0

            WHEN wind_speed_kmh <= wind_good_max_kmh
                THEN
                    80.0
                    - (
                        (wind_speed_kmh - wind_very_good_max_kmh)
                        / NULLIF(
                            wind_good_max_kmh
                            - wind_very_good_max_kmh,
                            0
                        )
                    ) * 40.0

            WHEN wind_speed_kmh <= wind_poor_max_kmh
                THEN
                    40.0
                    - (
                        (wind_speed_kmh - wind_good_max_kmh)
                        / NULLIF(
                            wind_poor_max_kmh
                            - wind_good_max_kmh,
                            0
                        )
                    ) * 30.0

            WHEN wind_speed_kmh <= wind_extreme_kmh
                THEN
                    10.0
                    - (
                        (wind_speed_kmh - wind_poor_max_kmh)
                        / NULLIF(
                            wind_extreme_kmh - wind_poor_max_kmh,
                            0
                        )
                    ) * 10.0

            ELSE 0.0

        END AS wind_speed_index

    FROM base
),

wind_direction_matches AS (

    SELECT
        w.*,
        d.preferred_wind_direction_score

    FROM wind_speed_scored AS w

    LEFT JOIN direction_scores AS d
        ON w.spot_id = d.spot_id
        AND w.observation_time = d.observation_time
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

wind_base_scored AS (

    SELECT
        *,

        (
            wind_direction_index * 0.60
            + wind_speed_index * 0.40
        ) AS wind_base

    FROM wind_direction_scored
),

wind_scored AS (

    SELECT
        *,

        CASE
            WHEN wind_base IS NULL THEN NULL

            ELSE LEAST(
                100.0,
                GREATEST(
                    0.0,
                    CASE
                        WHEN wind_direction_index < 30
                            AND wind_speed_index < 30
                            THEN wind_base * 0.60

                        WHEN wind_direction_index < 50
                            AND wind_speed_index < 50
                            THEN wind_base * 0.75

                        ELSE wind_base
                    END
                )
            )
        END AS wind_index

    FROM wind_base_scored
),

swell_direction_matches AS (

    SELECT
        w.*,
        d.preferred_swell_direction_score

    FROM wind_scored AS w

    LEFT JOIN direction_scores AS d
        ON w.spot_id = d.spot_id
        AND w.observation_time = d.observation_time
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

            ELSE GREATEST(
                0.0,
                LEAST(
                    100.0,
                    CASE
                        WHEN swell_height_m < swell_height_low_max_m
                            THEN
                                30.0 * GREATEST(0.0, swell_height_m)
                                / NULLIF(swell_height_low_max_m, 0)

                        WHEN swell_height_m <= swell_height_optimal_min_m
                            THEN
                                30.0
                                + (
                                    (swell_height_m - swell_height_low_max_m)
                                    / NULLIF(
                                        swell_height_optimal_min_m
                                        - swell_height_low_max_m,
                                        0
                                    )
                                ) * 35.0

                        WHEN swell_height_m <= (
                            swell_height_optimal_min_m
                            + swell_height_optimal_max_m
                        ) / 2.0
                            THEN
                                65.0
                                + (
                                    (
                                        swell_height_m
                                        - swell_height_optimal_min_m
                                    )
                                    / NULLIF(
                                        (
                                            swell_height_optimal_min_m
                                            + swell_height_optimal_max_m
                                        ) / 2.0
                                        - swell_height_optimal_min_m,
                                        0
                                    )
                                ) * 35.0

                        WHEN swell_height_m <= swell_height_optimal_max_m
                            THEN
                                100.0
                                - (
                                    (
                                        swell_height_m
                                        - (
                                            swell_height_optimal_min_m
                                            + swell_height_optimal_max_m
                                        ) / 2.0
                                    )
                                    / NULLIF(
                                        swell_height_optimal_max_m
                                        - (
                                            swell_height_optimal_min_m
                                            + swell_height_optimal_max_m
                                        ) / 2.0,
                                        0
                                    )
                                ) * 35.0

                        WHEN swell_height_m <= swell_height_large_min_m
                            THEN
                                65.0
                                - (
                                    (swell_height_m - swell_height_optimal_max_m)
                                    / NULLIF(
                                        swell_height_large_min_m
                                        - swell_height_optimal_max_m,
                                        0
                                    )
                                ) * 20.0

                        WHEN swell_height_m <= swell_height_extreme_min_m
                            THEN
                                45.0
                                - (
                                    (swell_height_m - swell_height_large_min_m)
                                    / NULLIF(
                                        swell_height_extreme_min_m
                                        - swell_height_large_min_m,
                                        0
                                    )
                                ) * 35.0

                        ELSE
                            10.0 * swell_height_extreme_min_m
                            / NULLIF(swell_height_m, 0)
                    END
                )
            )
        END AS swell_height_index

    FROM swell_direction_scored
),

swell_period_scored AS (

    SELECT
        sh.*,

        CASE
            WHEN sh.swell_period_s IS NULL
                THEN NULL

            ELSE GREATEST(
                0.0,
                LEAST(
                    100.0,
                    CASE
                        WHEN sh.swell_period_s < sp.period_too_short_s
                            THEN
                                30.0 * GREATEST(0.0, sh.swell_period_s)
                                / NULLIF(sp.period_too_short_s, 0)

                        WHEN sh.swell_period_s <= sp.period_optimal_min_s
                            THEN
                                30.0
                                + (
                                    (sh.swell_period_s - sp.period_too_short_s)
                                    / NULLIF(
                                        sp.period_optimal_min_s
                                        - sp.period_too_short_s,
                                        0
                                    )
                                ) * 35.0

                        WHEN sh.swell_period_s <= (
                            sp.period_optimal_min_s
                            + sp.period_optimal_max_s
                        ) / 2.0
                            THEN
                                65.0
                                + (
                                    (
                                        sh.swell_period_s
                                        - sp.period_optimal_min_s
                                    )
                                    / NULLIF(
                                        (
                                            sp.period_optimal_min_s
                                            + sp.period_optimal_max_s
                                        ) / 2.0
                                        - sp.period_optimal_min_s,
                                        0
                                    )
                                ) * 35.0

                        WHEN sh.swell_period_s <= sp.period_optimal_max_s
                            THEN
                                100.0
                                - (
                                    (
                                        sh.swell_period_s
                                        - (
                                            sp.period_optimal_min_s
                                            + sp.period_optimal_max_s
                                        ) / 2.0
                                    )
                                    / NULLIF(
                                        sp.period_optimal_max_s
                                        - (
                                            sp.period_optimal_min_s
                                            + sp.period_optimal_max_s
                                        ) / 2.0,
                                        0
                                    )
                                ) * 35.0

                        WHEN sh.swell_period_s <= sp.period_too_long_s
                            THEN
                                65.0
                                - (
                                    (sh.swell_period_s - sp.period_optimal_max_s)
                                    / NULLIF(
                                        sp.period_too_long_s
                                        - sp.period_optimal_max_s,
                                        0
                                    )
                                ) * 20.0

                        ELSE
                            45.0 * sp.period_too_long_s
                            / NULLIF(sh.swell_period_s, 0)
                    END
                )
            )
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
            swell_height_index * 0.50
            + swell_period_index * 0.25
            + calculated_swell_direction_index * 0.25
        ) AS swell_index

    FROM size_scored
),

tide_trend_observations AS (

    SELECT
        spot_id,
        observation_time,
        water_level_m,
        CASE
            WHEN tide_rate_m_per_hour > 0.01 THEN 1
            WHEN tide_rate_m_per_hour < -0.01 THEN -1
        END AS tide_direction

    FROM base

    WHERE water_level_m IS NOT NULL
      AND (
          tide_rate_m_per_hour > 0.01
          OR tide_rate_m_per_hour < -0.01
      )
),

tide_trend_changes AS (

    SELECT
        *,
        LAG(observation_time) OVER (
            PARTITION BY spot_id
            ORDER BY observation_time
        ) AS previous_observation_time,
        LAG(water_level_m) OVER (
            PARTITION BY spot_id
            ORDER BY observation_time
        ) AS previous_water_level_m,
        LAG(tide_direction) OVER (
            PARTITION BY spot_id
            ORDER BY observation_time
        ) AS previous_tide_direction

    FROM tide_trend_observations
),

tide_turning_points AS (

    SELECT
        spot_id,
        previous_observation_time AS turning_time,
        previous_water_level_m AS turning_level

    FROM tide_trend_changes

    WHERE (previous_tide_direction = 1 AND tide_direction = -1)
       OR (previous_tide_direction = -1 AND tide_direction = 1)
),

tide_bounds AS (

    SELECT
        c.*,
        previous_turn.turning_time AS previous_turning_time,
        previous_turn.turning_level AS previous_turning_level,
        next_turn.turning_time AS next_turning_time,
        next_turn.turning_level AS next_turning_level

    FROM swell_scored AS c

    LEFT JOIN LATERAL (
        SELECT
            turning_time,
            turning_level
        FROM tide_turning_points AS tp
        WHERE tp.spot_id = c.spot_id
          AND tp.turning_time <= c.observation_time
        ORDER BY tp.turning_time DESC
        LIMIT 1
    ) AS previous_turn ON TRUE

    LEFT JOIN LATERAL (
        SELECT
            turning_time,
            turning_level
        FROM tide_turning_points AS tp
        WHERE tp.spot_id = c.spot_id
          AND tp.turning_time > c.observation_time
        ORDER BY tp.turning_time
        LIMIT 1
    ) AS next_turn ON TRUE
),

tide_positions AS (

    SELECT
        *,
        CASE
            WHEN water_level_m IS NULL
                OR previous_turning_time IS NULL
                OR next_turning_time IS NULL
                OR GREATEST(previous_turning_level, next_turning_level)
                    <= LEAST(previous_turning_level, next_turning_level)
                THEN NULL

            ELSE LEAST(
                1.0,
                GREATEST(
                    0.0,
                    (
                        water_level_m
                        - LEAST(previous_turning_level, next_turning_level)
                    )
                    / NULLIF(
                        GREATEST(previous_turning_level, next_turning_level)
                        - LEAST(previous_turning_level, next_turning_level),
                        0
                    )
                )
            )
        END AS tide_position

    FROM tide_bounds
),

tide_scored AS (

    SELECT
        s.*,

        CASE
            WHEN s.tide_position IS NULL
                OR s.tide_low_score IS NULL
                OR s.tide_low_mid_score IS NULL
                OR s.tide_mid_score IS NULL
                OR s.tide_high_mid_score IS NULL
                OR s.tide_high_score IS NULL
                THEN NULL

            ELSE LEAST(
                100.0,
                GREATEST(
                    0.0,
                    CASE
                        WHEN s.tide_position <= 0.25
                            THEN s.tide_low_score
                                + (s.tide_position / 0.25)
                                * (s.tide_low_mid_score - s.tide_low_score)
                        WHEN s.tide_position <= 0.50
                            THEN s.tide_low_mid_score
                                + ((s.tide_position - 0.25) / 0.25)
                                * (s.tide_mid_score - s.tide_low_mid_score)
                        WHEN s.tide_position <= 0.75
                            THEN s.tide_mid_score
                                + ((s.tide_position - 0.50) / 0.25)
                                * (s.tide_high_mid_score - s.tide_mid_score)
                        ELSE s.tide_high_mid_score
                            + ((s.tide_position - 0.75) / 0.25)
                            * (s.tide_high_score - s.tide_high_mid_score)
                    END
                )
            )
        END AS tide_index

    FROM tide_positions AS s
),

surf_scored AS (

    SELECT
        *,

        CASE
            WHEN swell_index IS NULL
                OR wind_index IS NULL
                OR tide_index IS NULL
                THEN NULL

            ELSE LEAST(
                100.0,
                GREATEST(
                    0.0,
                    swell_index * 0.60
                    + wind_index * 0.25
                    + tide_index * 0.15
                )
            )
        END AS surf_index

    FROM tide_scored
),

surf_classified AS (

    SELECT
        *,

        CASE
            WHEN surf_index IS NULL THEN NULL

            WHEN surf_index >= 85
                AND swell_index >= 75
                AND wind_index >= 70
                AND tide_index >= 50
                THEN 'EXCELLENT'

            WHEN surf_index >= 70
                THEN 'VERY_GOOD'

            WHEN surf_index >= 50
                THEN 'GOOD'

            WHEN surf_index >= 30
                THEN 'FAIR'

            ELSE 'POOR'

        END AS surf_quality_band

    FROM surf_scored
),

tide_availability AS (

    SELECT
        *,

        -- Last hour per spot with a reliable (non-interpolation-failed) tide_index
        MAX(observation_time) FILTER (
            WHERE tide_index IS NOT NULL
        ) OVER (PARTITION BY spot_id) AS last_reliable_tide_observation_time

    FROM surf_classified
)
,

expected_hours AS (
    -- Local midnight boundaries preserve 23/25-hour daylight-saving days.
    SELECT d.spot_id, d.observation_date AS local_date, h.observation_time
    FROM {{ ref('stg_sunrise_sunset') }} AS d
    INNER JOIN {{ ref('stg_surf_spots') }} AS spot USING (spot_id)
    CROSS JOIN LATERAL GENERATE_SERIES(
        d.observation_date::timestamp AT TIME ZONE spot.timezone,
        (d.observation_date + 1)::timestamp AT TIME ZONE spot.timezone
            - INTERVAL '1 hour',
        INTERVAL '1 hour'
    ) AS h(observation_time)
),

complete_days AS (
    -- Check expected hours, not just rows that survived the source joins.
    SELECT e.spot_id, e.local_date
    FROM expected_hours AS e
    LEFT JOIN tide_availability AS c
        ON c.spot_id = e.spot_id
        AND c.observation_time = e.observation_time
    GROUP BY e.spot_id, e.local_date
    HAVING BOOL_AND(
        COALESCE(
            c.observation_time >= CURRENT_DATE
            AND c.observation_time < CURRENT_DATE + INTERVAL '7 days'
            AND c.local_date = e.local_date
            AND c.first_light IS NOT NULL
            AND c.last_light IS NOT NULL
            AND c.sunrise IS NOT NULL
            AND c.sunset IS NOT NULL
            AND c.wave_height_m IS NOT NULL
            AND c.wave_period_s IS NOT NULL
            AND c.wave_direction_deg IS NOT NULL
            AND c.swell_height_m IS NOT NULL
            AND c.swell_period_s IS NOT NULL
            AND c.swell_direction_deg IS NOT NULL
            AND c.wind_speed_kmh IS NOT NULL
            AND c.wind_gusts_kmh IS NOT NULL
            AND c.wind_direction_deg IS NOT NULL
            AND c.sea_surface_temperature_c IS NOT NULL
            AND c.water_level_m IS NOT NULL
            AND c.tide_rate_m_per_hour IS NOT NULL
            AND c.tide_phase <> 'UNKNOWN'
            AND c.wind_speed_index IS NOT NULL
            AND c.wind_direction_index IS NOT NULL
            AND c.wind_index IS NOT NULL
            AND c.swell_height_index IS NOT NULL
            AND c.swell_period_index IS NOT NULL
            AND c.calculated_swell_direction_index IS NOT NULL
            AND c.size_index IS NOT NULL
            AND c.swell_index IS NOT NULL
            AND c.tide_position IS NOT NULL
            AND c.tide_index IS NOT NULL
            AND c.surf_index IS NOT NULL,
            FALSE
        )
    )
    AND COUNT(*) FILTER (WHERE c.is_surfable_light) > 0
)

SELECT c.*
FROM tide_availability AS c
INNER JOIN complete_days AS d
    ON c.spot_id = d.spot_id AND c.local_date = d.local_date
