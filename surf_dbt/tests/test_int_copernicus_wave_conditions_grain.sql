SELECT
    spot_id,
    observation_time,
    COUNT(*) AS row_count

FROM {{ ref('int_copernicus_wave_conditions') }}

GROUP BY
    spot_id,
    observation_time

HAVING COUNT(*) > 1