SELECT
    id,

    event_id,
    event_name,
    event_date,

    spot_id,

    tour,
    round,
    heat_number,

    surfer_id,
    surfer_name,
    surfer_country,

    heat_score,
    waves_count,

    best_wave_1,
    best_wave_2,

    ingested_at

FROM {{ source('wsl', 'wsl_performance') }}