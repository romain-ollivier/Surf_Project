SELECT
    id,
    spot_id,

    latitude,
    longitude,
    elevation,

    observation_time,

    wave_height AS wave_height_m,
    wave_direction AS wave_direction_deg,
    wave_period AS wave_period_s,
    wave_peak_period AS wave_peak_period_s,

    wind_wave_height AS wind_wave_height_m,
    wind_wave_direction AS wind_wave_direction_deg,
    wind_wave_period AS wind_wave_period_s,
    wind_wave_peak_period AS wind_wave_peak_period_s,

    swell_wave_height AS swell_height_m,
    swell_wave_direction AS swell_direction_deg,
    swell_wave_period AS swell_period_s,
    swell_wave_peak_period AS swell_peak_period_s,

    sea_surface_temperature AS sea_surface_temperature_c,
    sea_level_height_msl,

    ocean_current_velocity AS ocean_current_velocity_ms,
    ocean_current_direction AS ocean_current_direction_deg,

    ingested_at

FROM {{ source('open_meteo', 'open_meteo_marine') }}