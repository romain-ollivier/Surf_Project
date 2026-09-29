SELECT
    spot_id,
    observation_time,
    wave_period_s

FROM {{ ref('int_surf_conditions') }}

WHERE wave_period_s <= 0
