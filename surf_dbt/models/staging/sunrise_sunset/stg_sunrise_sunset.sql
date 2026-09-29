SELECT
    id,
    spot_id,

    observation_date,

    timezone,
    utc_offset,

    latitude,
    longitude,

    sunrise,
    sunset,

    dawn,
    dusk,

    first_light,
    last_light,

    civil_twilight_begin,
    civil_twilight_end,

    day_length_seconds,

    ingested_at

FROM {{ source('sunrise_sunset', 'sunrise_sunset') }}