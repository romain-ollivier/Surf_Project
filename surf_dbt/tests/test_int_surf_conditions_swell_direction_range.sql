SELECT
    spot_id,
    observation_time,
    swell_direction_deg

FROM {{ ref('int_surf_conditions') }}

WHERE swell_direction_deg < 0
   OR swell_direction_deg > 360
