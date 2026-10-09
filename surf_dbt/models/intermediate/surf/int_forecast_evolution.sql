-- Forecast evolution: historical horizon minus latest available forecast.
-- These differences are revisions, not errors against field observations.
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
    -- Latest forecast reference
    -- =====================================================

    a.air_temperature_c AS latest_forecast_air_temperature_c,
    a.wind_speed_kmh AS latest_forecast_wind_speed_kmh,
    a.wind_direction_deg AS latest_forecast_wind_direction_deg,
    a.wind_gusts_kmh AS latest_forecast_wind_gusts_kmh,
    a.precipitation_mm AS latest_forecast_precipitation_mm,
    a.cloud_cover_pct AS latest_forecast_cloud_cover_pct,

    -- =====================================================
    -- Forecast revisions
    -- =====================================================

    f.air_temperature_c
        - a.air_temperature_c
        AS temperature_revision_c,

    ABS(
        f.air_temperature_c
        - a.air_temperature_c
    ) AS temperature_absolute_revision_c,

    f.wind_speed_kmh
        - a.wind_speed_kmh
        AS wind_speed_revision_kmh,

    ABS(
        f.wind_speed_kmh
        - a.wind_speed_kmh
    ) AS wind_speed_absolute_revision_kmh,

    f.wind_gusts_kmh
        - a.wind_gusts_kmh
        AS wind_gusts_revision_kmh,

    ABS(
        f.wind_gusts_kmh
        - a.wind_gusts_kmh
    ) AS wind_gusts_absolute_revision_kmh,

    f.precipitation_mm
        - a.precipitation_mm
        AS precipitation_revision_mm,

    ABS(
        f.precipitation_mm
        - a.precipitation_mm
    ) AS precipitation_absolute_revision_mm,

    f.cloud_cover_pct
        - a.cloud_cover_pct
        AS cloud_cover_revision_pct,

    ABS(
        f.cloud_cover_pct
        - a.cloud_cover_pct
    ) AS cloud_cover_absolute_revision_pct

FROM {{ ref('stg_open_meteo_forecast') }} AS f

INNER JOIN {{ ref('int_surf_conditions') }} AS a
    ON f.spot_id = a.spot_id
    AND f.observation_time = a.observation_time

INNER JOIN {{ ref('stg_surf_spots') }} AS s
    ON f.spot_id = s.spot_id