WITH hourly AS (

    SELECT *
    FROM {{ ref('fct_surf_hourly') }}
    WHERE is_surfable_light

),

ranked_hours AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY
                spot_id,
                local_date
            ORDER BY
                surf_index DESC NULLS LAST,
                local_observation_time ASC
        ) AS hour_rank

    FROM hourly

),

daily AS (

    SELECT
        spot_id,
        spot_name,
        timezone,
        local_date,
        local_date AS forecast_date,

        -- Surf Index
        AVG(surf_index) AS surf_index_avg,
        AVG(swell_index) AS swell_index_avg,
        AVG(wind_index) AS wind_index_avg,
        AVG(tide_index) AS tide_index_avg,
        MIN(surf_index) AS surf_index_min,
        MAX(surf_index) AS surf_index_max,

        -- Number of scored hours
        COUNT(surf_index) AS scored_hours,

        -- Quality bands
        COUNT(*) FILTER (
            WHERE surf_quality_band = 'EXCELLENT'
        ) AS excellent_hours,

        COUNT(*) FILTER (
            WHERE surf_quality_band = 'VERY_GOOD'
        ) AS very_good_hours,

        COUNT(*) FILTER (
            WHERE surf_quality_band = 'GOOD'
        ) AS good_hours,

        COUNT(*) FILTER (
            WHERE surf_quality_band = 'POOR'
        ) AS poor_hours,

        COUNT(*) FILTER (
            WHERE surf_quality_band = 'FAIR'
        ) AS fair_hours,

        -- Best hour
        MAX(
            CASE
                WHEN hour_rank = 1
                    THEN local_observation_time
            END
        ) AS best_hour,

        MAX(
            CASE
                WHEN hour_rank = 1
                    THEN surf_index
            END
        ) AS best_surf_index,

        -- Average physical conditions
        AVG(wave_height_m) AS avg_wave_height_m,
        AVG(swell_height_m) AS avg_swell_height_m,
        AVG(swell_period_s) AS avg_swell_period_s,
        AVG(wind_speed_kmh) AS avg_wind_speed_kmh,
        AVG(water_level_m) AS avg_tide_level_m

    FROM ranked_hours

    GROUP BY
        spot_id,
        spot_name,
        timezone,
        local_date

),

classified AS (

    SELECT
        *,

        CASE
            WHEN surf_index_avg >= 85
                AND swell_index_avg >= 75
                AND wind_index_avg >= 70
                AND tide_index_avg >= 50 THEN 'EXCELLENT'
            WHEN surf_index_avg >= 70 THEN 'VERY_GOOD'
            WHEN surf_index_avg >= 50 THEN 'GOOD'
            WHEN surf_index_avg >= 30 THEN 'FAIR'
            ELSE 'POOR'
        END AS surf_quality_band

    FROM daily

)

SELECT *
FROM classified