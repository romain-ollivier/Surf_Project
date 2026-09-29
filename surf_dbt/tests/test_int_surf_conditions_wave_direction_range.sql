SELECT
    spot_id,
    observation_time,
    wave_direction_deg

FROM {{ ref('int_surf_conditions') }}

WHERE wave_direction_deg < 0
   OR wave_direction_deg > 360
