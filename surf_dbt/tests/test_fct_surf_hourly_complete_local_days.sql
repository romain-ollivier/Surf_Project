-- A published day must contain every UTC instant between its local midnights.
WITH days AS (
    SELECT spot_id, local_date, timezone, COUNT(*) AS actual_hours,
        COUNT(DISTINCT observation_time) AS distinct_hours
    FROM {{ ref('fct_surf_hourly') }}
    GROUP BY spot_id, local_date, timezone
)
SELECT * FROM days
WHERE actual_hours <> EXTRACT(EPOCH FROM (
    (local_date + 1)::timestamp AT TIME ZONE timezone
    - (local_date::timestamp AT TIME ZONE timezone)
)) / 3600
OR actual_hours <> distinct_hours
