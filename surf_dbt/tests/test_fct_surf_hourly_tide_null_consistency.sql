SELECT
    spot_id,
    observation_time,
    water_level_m,
    tide_position,
    tide_index

FROM {{ ref('fct_surf_hourly') }}

WHERE (
        water_level_m IS NULL
        AND (tide_position IS NOT NULL OR tide_index IS NOT NULL)
    )
    OR (tide_position IS NULL AND tide_index IS NOT NULL)
    OR (tide_position IS NOT NULL AND tide_index IS NULL)