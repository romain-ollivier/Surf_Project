SELECT
    spot_id,
    observation_time,
    swell_period_s

FROM {{ ref('int_surf_conditions') }}

WHERE swell_period_s <= 0
