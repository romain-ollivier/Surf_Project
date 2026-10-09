-- Every expected surfable hour must be present; night hours are irrelevant.
WITH published_days AS (
    SELECT DISTINCT spot_id, local_date
    FROM {{ ref('fct_surf_hourly') }}
),
expected AS (
    SELECT d.spot_id, d.local_date, h.observation_time
    FROM published_days AS d
    INNER JOIN {{ ref('stg_surf_spots') }} AS spot USING (spot_id)
    INNER JOIN {{ ref('stg_sunrise_sunset') }} AS sun
        ON sun.spot_id = d.spot_id AND sun.observation_date = d.local_date
    CROSS JOIN LATERAL GENERATE_SERIES(
        d.local_date::timestamp AT TIME ZONE spot.timezone,
        (d.local_date + 1)::timestamp AT TIME ZONE spot.timezone - INTERVAL '1 hour',
        INTERVAL '1 hour'
    ) AS h(observation_time)
    WHERE h.observation_time >= sun.first_light
      AND h.observation_time <= sun.last_light
)
SELECT e.*
FROM expected AS e
LEFT JOIN {{ ref('fct_surf_hourly') }} AS actual
    ON actual.spot_id = e.spot_id AND actual.observation_time = e.observation_time
WHERE actual.observation_time IS NULL
UNION ALL
SELECT spot_id, local_date, observation_time
FROM {{ ref('fct_surf_hourly') }}
WHERE NOT is_surfable_light
