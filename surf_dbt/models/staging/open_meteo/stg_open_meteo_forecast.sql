SELECT
    id,
    spot_id,

    latitude,
    longitude,

    observation_time,

    forecast_horizon_days,

    temperature_2m AS air_temperature_c,

    wind_speed_10m AS wind_speed_kmh,
    wind_direction_10m AS wind_direction_deg,
    wind_gusts_10m AS wind_gusts_kmh,

    precipitation AS precipitation_mm,

    cloud_cover AS cloud_cover_pct,

    ingested_at

FROM {{ source('open_meteo', 'open_meteo_forecast_history') }}