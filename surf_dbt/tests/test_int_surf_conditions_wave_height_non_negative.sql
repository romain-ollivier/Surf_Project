SELECT
    spot_id,
    observation_time,
    wave_height_m

FROM {{ ref('int_surf_conditions') }}

WHERE wave_height_m < 0
