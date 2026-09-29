SELECT
    tide_station_id,
    spot_id,

    station_name,

    latitude,
    longitude,
    distance_to_spot_km,

    source,
    license,
    commercial_use,

    station_type,
    timezone,
    chart_datum,
    datums_source,

    ingested_at

FROM {{ source('tides', 'tide_stations') }}