SELECT
    spot_id,
    observation_time,
    swell_height_m

FROM {{ ref('int_surf_conditions') }}

WHERE swell_height_m < 0
