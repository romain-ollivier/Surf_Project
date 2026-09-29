SELECT
    id,
    tide_station_id,

    observation_time,

    water_level_m,
    datum,
    units,

    ingested_at

FROM {{ source('tides', 'open_waters_tides') }}