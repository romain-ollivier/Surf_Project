SELECT
    spot_id,
    spot_name,
    country,
    region,
    latitude,
    longitude,
    timezone

FROM {{ ref('surf_spots') }}