SELECT
    spot_id,
    spot_name,
    country,
    region,
    latitude,
    longitude,
    ingested_at

FROM {{ source('surf', 'surf_spots') }}