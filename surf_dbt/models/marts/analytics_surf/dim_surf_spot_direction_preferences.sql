SELECT
    spot_id,
    direction_type,
    direction_min_deg,
    direction_max_deg,
    preference_level,
    source
FROM {{ ref('surf_spot_direction_preferences') }}