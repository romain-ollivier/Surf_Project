WITH hourly_candidates AS (

    SELECT
        tide_station_id,
        observation_time,
        water_level_m,
        datum,
        units,

        DATE_TRUNC(
            'hour',
            observation_time
        ) AS hour,

        ABS(
            EXTRACT(
                EPOCH FROM (
                    observation_time
                    - DATE_TRUNC('hour', observation_time)
                )
            )
        ) AS seconds_from_hour

    FROM {{ ref('stg_open_waters_tides') }}

),

ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY
                tide_station_id,
                hour
            ORDER BY
                seconds_from_hour,
                observation_time
        ) AS rn

    FROM hourly_candidates

)

SELECT
    tide_station_id,
    hour AS observation_time,
    water_level_m,
    datum,
    units

FROM ranked

WHERE rn = 1