SELECT spot_id
FROM {{ source('tides', 'tide_stations') }}
GROUP BY spot_id
HAVING COUNT(*) FILTER (WHERE is_active) <> 1
