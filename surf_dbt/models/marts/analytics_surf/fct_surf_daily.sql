WITH hourly AS (

    SELECT *
    FROM {{ ref('fct_surf_hourly') }}

),

ranked_hours AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY
                spot_id,
                observation_time::date
            ORDER BY
                surf_index DESC,
                observation_time ASC
        ) AS hour_rank

    FROM hourly

),

daily AS (

    SELECT
        spot_id,
        spot_name,
        observation_time::date AS forecast_date,

        -- Surf Index
        AVG(surf_index) AS surf_index_avg,
        MIN(surf_index) AS surf_index_min,
        MAX(surf_index) AS surf_index_max,

        -- Number of scored hours
        COUNT(*) AS scored_hours,

        -- Quality bands
        COUNT(*) FILTER (
            WHERE surf_quality_band = 'OPTIMAL'
        ) AS optimal_hours,

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
            WHERE surf_quality_band = 'VERY_POOR'
        ) AS very_poor_hours,

        -- Best hour
        MAX(
            CASE
                WHEN hour_rank = 1
                    THEN observation_time
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
        observation_time::date

),

classified AS (

    SELECT
        *,

        CASE
            WHEN surf_index_avg < 20
                THEN 'VERY_POOR'

            WHEN surf_index_avg < 40
                THEN 'POOR'

            WHEN surf_index_avg < 60
                THEN 'GOOD'

            WHEN surf_index_avg < 80
                THEN 'VERY_GOOD'

            ELSE 'OPTIMAL'
        END AS surf_quality_band

    FROM daily

)

SELECT *
FROM classified