SELECT a.spot_id, a.tide_station_id, b.tide_station_id AS conflicting_station
FROM {{ source('tides', 'tide_stations') }} a
JOIN {{ source('tides', 'tide_stations') }} b
 ON a.spot_id = b.spot_id AND a.tide_station_id < b.tide_station_id
 AND COALESCE(a.valid_from, '-infinity'::timestamptz) < COALESCE(b.valid_to, 'infinity'::timestamptz)
 AND COALESCE(b.valid_from, '-infinity'::timestamptz) < COALESCE(a.valid_to, 'infinity'::timestamptz)
