WITH base AS (

    SELECT
        s.spot_id,
        s.spot_name,
        s.timezone,
        w.observation_time,

        -- Weather
        w.air_temperature_c,
        w.precipitation_mm,
        w.cloud_cover_pct,
        w.visibility_m,
        w.wind_speed_kmh,
        w.wind_direction_deg,
        w.wind_gusts_kmh,

        -- Spot
        c.break_orientation_deg,

        -- Wave
        m.wave_height_m,
        m.wave_direction_deg,
        m.wave_period_s,
        m.wave_peak_period_s,

        -- Wind wave
        m.wind_wave_height_m,
        m.wind_wave_direction_deg,
        m.wind_wave_period_s,
        m.wind_wave_peak_period_s,

        -- Swell
        m.swell_height_m,
        m.swell_direction_deg,
        m.swell_period_s,
        m.swell_peak_period_s,

        -- Ocean
        m.sea_surface_temperature_c

    FROM {{ ref('stg_surf_spots') }} AS s

    INNER JOIN {{ ref('surf_spot_characteristics') }} AS c
        ON s.spot_id = c.spot_id

    INNER JOIN {{ ref('stg_open_meteo_weather') }} AS w
        ON s.spot_id = w.spot_id

    INNER JOIN {{ ref('stg_open_meteo_marine') }} AS m
        ON s.spot_id = m.spot_id
        AND w.observation_time = m.observation_time
),

wind_conditions AS (

    SELECT
        *,

        -- Direction du vent offshore par rapport à l'orientation du spot
        MOD(
            (break_orientation_deg + 180)::numeric,
            360
        ) AS offshore_wind_direction_deg,

        -- Écart angulaire entre le vent et la direction offshore
        LEAST(
            ABS(
                wind_direction_deg
                - MOD(
                    (break_orientation_deg + 180)::numeric,
                    360
                )
            ),
            360 - ABS(
                wind_direction_deg
                - MOD(
                    (break_orientation_deg + 180)::numeric,
                    360
                )
            )
        ) AS wind_relative_angle_deg,

        -- Classification physique de l'orientation du vent
        CASE
            WHEN wind_direction_deg IS NULL
                THEN 'UNKNOWN'

            WHEN LEAST(
                ABS(
                    wind_direction_deg
                    - MOD(
                        (break_orientation_deg + 180)::numeric,
                        360
                    )
                ),
                360 - ABS(
                    wind_direction_deg
                    - MOD(
                        (break_orientation_deg + 180)::numeric,
                        360
                    )
                )
            ) <= 45
                THEN 'OFFSHORE'

            WHEN LEAST(
                ABS(
                    wind_direction_deg
                    - MOD(
                        (break_orientation_deg + 180)::numeric,
                        360
                    )
                ),
                360 - ABS(
                    wind_direction_deg
                    - MOD(
                        (break_orientation_deg + 180)::numeric,
                        360
                    )
                )
            ) <= 135
                THEN 'CROSS_SHORE'

            ELSE 'ONSHORE'
        END AS wind_condition

    FROM base
),

swell_windows AS (

    SELECT
        spot_id,
        direction_min_deg,
        direction_max_deg,

        CASE
            -- Fenêtre normale, par exemple 270° → 315°
            WHEN direction_min_deg <= direction_max_deg
                THEN (
                    direction_min_deg
                    + direction_max_deg
                ) / 2.0

            -- Fenêtre traversant 0°, par exemple 337.5° → 22.5°
            ELSE
                (
                    direction_min_deg
                    + direction_max_deg
                    + 360.0
                ) / 2.0
                - 360.0

        END AS window_center_deg

    FROM {{ ref('surf_spot_direction_preferences') }}

    WHERE direction_type = 'SWELL'
),

swell_alignment AS (

    SELECT
        wc.*,

        -- Distance angulaire minimale par rapport
        -- aux fenêtres de swell préférées du spot
        MIN(
            LEAST(
                ABS(
                    wc.swell_direction_deg
                    - sw.window_center_deg
                ),
                360 - ABS(
                    wc.swell_direction_deg
                    - sw.window_center_deg
                )
            )
        ) AS swell_direction_alignment_deg

    FROM wind_conditions AS wc

    LEFT JOIN swell_windows AS sw
        ON wc.spot_id = sw.spot_id

    GROUP BY
        wc.spot_id,
        wc.spot_name,
        wc.timezone,
        wc.observation_time,
        wc.air_temperature_c,
        wc.precipitation_mm,
        wc.cloud_cover_pct,
        wc.visibility_m,
        wc.wind_speed_kmh,
        wc.wind_direction_deg,
        wc.wind_gusts_kmh,
        wc.break_orientation_deg,
        wc.wave_height_m,
        wc.wave_direction_deg,
        wc.wave_period_s,
        wc.wave_peak_period_s,
        wc.wind_wave_height_m,
        wc.wind_wave_direction_deg,
        wc.wind_wave_period_s,
        wc.wind_wave_peak_period_s,
        wc.swell_height_m,
        wc.swell_direction_deg,
        wc.swell_period_s,
        wc.swell_peak_period_s,
        wc.offshore_wind_direction_deg,
        wc.wind_relative_angle_deg,
        wc.wind_condition,
        wc.sea_surface_temperature_c
),

tide_base AS (

    SELECT
        ts.spot_id,
        t.observation_time,
        t.water_level_m

    FROM {{ ref('int_open_waters_tides_hourly') }} AS t

    INNER JOIN {{ ref('stg_tide_stations') }} AS ts
        ON t.tide_station_id = ts.tide_station_id
),

tide_features AS (

    SELECT
        spot_id,
        observation_time,
        water_level_m,

        water_level_m
        - LAG(water_level_m) OVER (
            PARTITION BY spot_id
            ORDER BY observation_time
        ) AS tide_rate_m_per_hour

    FROM tide_base
),

tide_classified AS (

    SELECT
        spot_id,
        observation_time,
        water_level_m,
        tide_rate_m_per_hour,

        CASE
            WHEN tide_rate_m_per_hour IS NULL
                THEN 'UNKNOWN'

            WHEN tide_rate_m_per_hour > 0.01
                THEN 'RISING'

            WHEN tide_rate_m_per_hour < -0.01
                THEN 'FALLING'

            ELSE 'STABLE'
        END AS tide_phase

    FROM tide_features
),

daylight_features AS (

    SELECT
        spot_id,
        observation_date,
        first_light,
        sunrise,
        sunset,
        last_light

    FROM {{ ref('stg_sunrise_sunset') }}
),

localized_conditions AS (

    SELECT
        sa.*,

        sa.observation_time AT TIME ZONE sa.timezone
            AS local_observation_time,

        (
            sa.observation_time AT TIME ZONE sa.timezone
        )::date AS local_date,

        -- Tide
        t.water_level_m,
        t.tide_rate_m_per_hour,
        t.tide_phase,

        -- Source values remain timestamptz instants; local values are wall time.
        d.first_light,
        d.sunrise,
        d.sunset,
        d.last_light,
        d.first_light AT TIME ZONE sa.timezone AS first_light_local,
        d.sunrise AT TIME ZONE sa.timezone AS sunrise_local,
        d.sunset AT TIME ZONE sa.timezone AS sunset_local,
        d.last_light AT TIME ZONE sa.timezone AS last_light_local

    FROM swell_alignment AS sa

    LEFT JOIN tide_classified AS t
        ON sa.spot_id = t.spot_id
        AND sa.observation_time = t.observation_time

    LEFT JOIN daylight_features AS d
        ON sa.spot_id = d.spot_id
        AND (
            sa.observation_time AT TIME ZONE sa.timezone
        )::date = d.observation_date
)

SELECT
    *,

    COALESCE(
        local_observation_time >= sunrise_local
            AND local_observation_time <= sunset_local,
        FALSE
    ) AS is_daylight,

    COALESCE(
        local_observation_time >= first_light_local
            AND local_observation_time <= last_light_local,
        FALSE
    ) AS is_surfable_light

FROM localized_conditions