SELECT
    spot_id,
    observation_time,
    wind_direction_deg

FROM {{ ref('int_surf_conditions') }}

WHERE wind_direction_deg < 0
   OR wind_direction_deg > 360
