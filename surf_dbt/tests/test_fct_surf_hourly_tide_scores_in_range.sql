SELECT
    spot_id,
    observation_time,
    tide_position,
    tide_index

FROM {{ ref('fct_surf_hourly') }}

WHERE tide_position < 0
   OR tide_position > 1
   OR tide_index < 0
   OR tide_index > 100