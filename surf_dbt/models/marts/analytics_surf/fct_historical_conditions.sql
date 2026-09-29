SELECT
    w.spot_id,
    s.spot_name,
    w.observation_time,

    -- Weather
    w.air_temperature_c,
    w.precipitation_mm,
    w.cloud_cover_pct,
    w.visibility_m,
    w.wind_speed_kmh,
    w.wind_direction_deg,
    w.wind_gusts_kmh,

    -- Marine
    m.wave_height_m,
    m.wave_direction_deg,
    m.wave_period_s,
    m.swell_height_m,
    m.swell_direction_deg,
    m.swell_period_s,
    m.sea_surface_temperature_c,

    -- Spot characteristics
    c.break_type,
    c.break_orientation_deg,
    c.tide_preference,
    c.preferred_period_min_s,
    c.difficulty

FROM {{ ref('stg_open_meteo_weather_history') }} AS w

INNER JOIN {{ ref('stg_open_meteo_marine_history') }} AS m
    ON w.spot_id = m.spot_id
    AND w.observation_time = m.observation_time

INNER JOIN {{ ref('stg_spots') }} AS s
    ON w.spot_id = s.spot_id

INNER JOIN {{ ref('surf_spot_characteristics') }} AS c
    ON w.spot_id = c.spot_id