SELECT

    -- =====================================================
    -- Spot
    -- =====================================================

    s.spot_id,
    s.spot_name,
    s.country,
    s.region,

    -- =====================================================
    -- Time
    -- =====================================================

    f.observation_time,
    f.forecast_horizon_days,

    -- =====================================================
    -- Forecast
    -- =====================================================

    f.air_temperature_c AS forecast_air_temperature_c,
    f.wind_speed_kmh AS forecast_wind_speed_kmh,
    f.wind_direction_deg AS forecast_wind_direction_deg,
    f.wind_gusts_kmh AS forecast_wind_gusts_kmh,
    f.precipitation_mm AS forecast_precipitation_mm,
    f.cloud_cover_pct AS forecast_cloud_cover_pct,

    -- =====================================================
    -- Actual observed conditions
    -- =====================================================

    a.air_temperature_c AS actual_air_temperature_c,
    a.wind_speed_kmh AS actual_wind_speed_kmh,
    a.wind_direction_deg AS actual_wind_direction_deg,
    a.wind_gusts_kmh AS actual_wind_gusts_kmh,
    a.precipitation_mm AS actual_precipitation_mm,
    a.cloud_cover_pct AS actual_cloud_cover_pct,

    -- =====================================================
    -- Forecast errors
    -- =====================================================

    f.air_temperature_c
        - a.air_temperature_c
        AS temperature_error_c,

    ABS(
        f.air_temperature_c
        - a.air_temperature_c
    ) AS temperature_absolute_error_c,

    f.wind_speed_kmh
        - a.wind_speed_kmh
        AS wind_speed_error_kmh,

    ABS(
        f.wind_speed_kmh
        - a.wind_speed_kmh
    ) AS wind_speed_absolute_error_kmh,

    f.wind_gusts_kmh
        - a.wind_gusts_kmh
        AS wind_gusts_error_kmh,

    ABS(
        f.wind_gusts_kmh
        - a.wind_gusts_kmh
    ) AS wind_gusts_absolute_error_kmh,

    f.precipitation_mm
        - a.precipitation_mm
        AS precipitation_error_mm,

    ABS(
        f.precipitation_mm
        - a.precipitation_mm
    ) AS precipitation_absolute_error_mm,

    f.cloud_cover_pct
        - a.cloud_cover_pct
        AS cloud_cover_error_pct,

    ABS(
        f.cloud_cover_pct
        - a.cloud_cover_pct
    ) AS cloud_cover_absolute_error_pct

FROM {{ ref('stg_open_meteo_forecast') }} AS f

INNER JOIN {{ ref('int_surf_conditions') }} AS a
    ON f.spot_id = a.spot_id
    AND f.observation_time = a.observation_time

INNER JOIN {{ ref('stg_surf_spots') }} AS s
    ON f.spot_id = s.spot_id