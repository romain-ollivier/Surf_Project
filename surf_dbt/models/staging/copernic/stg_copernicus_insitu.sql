SELECT
    id,
    spot_id,

    platform_id,

    latitude,
    longitude,

    observation_time,

    variable,
    value,
    value_qc,

    institution,
    doi,
    product_doi,

    ingested_at

FROM {{ source('copernicus', 'copernicus_insitu') }}