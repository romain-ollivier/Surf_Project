SELECT
    s.spot_id,
    s.spot_name,
    s.country,
    s.region,
    s.latitude,
    s.longitude,
    c.break_type,
    c.break_orientation_deg,
    c.tide_preference,
    c.preferred_period_min_s,
    c.difficulty,
    c.source
FROM {{ ref('stg_spots') }} AS s
INNER JOIN {{ ref('surf_spot_characteristics') }} AS c
    ON s.spot_id = c.spot_id