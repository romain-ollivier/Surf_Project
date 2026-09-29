SELECT
    id,
    spot_id,
    latitude,
    longitude,
    observation_time,

    temperature_2m AS air_temperature_c,
    precipitation AS precipitation_mm,
    cloud_cover AS cloud_cover_pct,
    visibility AS visibility_m,
    wind_speed_10m AS wind_speed_kmh,
    wind_direction_10m AS wind_direction_deg,
    wind_gusts_10m AS wind_gusts_kmh,

    ingested_at

FROM {{ source('open_meteo_history', 'open_meteo_weather_history') }}