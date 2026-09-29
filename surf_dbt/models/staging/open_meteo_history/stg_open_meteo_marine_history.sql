SELECT
    id,
    spot_id,
    latitude,
    longitude,
    observation_time,

    wave_height AS wave_height_m,
    wave_direction AS wave_direction_deg,
    wave_period AS wave_period_s,

    swell_wave_height AS swell_height_m,
    swell_wave_direction AS swell_direction_deg,
    swell_wave_period AS swell_period_s,

    sea_surface_temperature AS sea_surface_temperature_c,

    ingested_at

FROM {{ source('open_meteo_history', 'open_meteo_marine_history') }}