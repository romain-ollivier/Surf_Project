SELECT
    id,
    spot_id,

    latitude,
    longitude,
    elevation,

    observation_time,

    temperature_2m AS air_temperature_c,
    apparent_temperature AS apparent_temperature_c,
    dew_point_2m AS dew_point_c,
    relative_humidity_2m AS relative_humidity_pct,

    precipitation AS precipitation_mm,
    rain AS rain_mm,
    showers AS showers_mm,
    snowfall AS snowfall_cm,

    weather_code,

    cloud_cover AS cloud_cover_pct,
    cloud_cover_low AS cloud_cover_low_pct,
    cloud_cover_mid AS cloud_cover_mid_pct,
    cloud_cover_high AS cloud_cover_high_pct,

    wind_speed_10m AS wind_speed_kmh,
    wind_direction_10m AS wind_direction_deg,
    wind_gusts_10m AS wind_gusts_kmh,

    pressure_msl AS pressure_msl_hpa,
    surface_pressure AS surface_pressure_hpa,
    visibility AS visibility_m,

    ingested_at

FROM {{ source('open_meteo', 'open_meteo_weather') }}