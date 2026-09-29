WITH source AS (

    SELECT *
    FROM {{ ref('stg_copernicus_insitu') }}

),

wave_conditions AS (

    SELECT
        spot_id,
        platform_id,
        observation_time,

        latitude,
        longitude,

        -- Significant wave height
        MAX(
            CASE
                WHEN variable = 'VHM0'
                THEN value
            END
        ) AS significant_wave_height_m,

        -- Peak wave period
        MAX(
            CASE
                WHEN variable = 'VTPK'
                THEN value
            END
        ) AS peak_wave_period_s,

        -- Mean wave direction
        MAX(
            CASE
                WHEN variable = 'VMDR'
                THEN value
            END
        ) AS mean_wave_direction_deg,

        -- Mean spectral wave period
        MAX(
            CASE
                WHEN variable = 'VTM02'
                THEN value
            END
        ) AS mean_wave_period_s,

        -- Water temperature
        MAX(
            CASE
                WHEN variable = 'TEMP'
                THEN value
            END
        ) AS sea_surface_temperature_c,

        -- Hossegor-specific observations
        MAX(
            CASE
                WHEN variable = 'VAVH'
                THEN value
            END
        ) AS average_upper_third_wave_height_m,

        MAX(
            CASE
                WHEN variable = 'VAVT'
                THEN value
            END
        ) AS average_upper_third_wave_period_s,

        MAX(
            CASE
                WHEN variable = 'VZMX'
                THEN value
            END
        ) AS maximum_wave_height_zero_crossing_m,

        MAX(
            CASE
                WHEN variable = 'VEMH'
                THEN value
            END
        ) AS estimated_maximum_wave_height_m,

        MAX(
            CASE
                WHEN variable = 'VGHS'
                THEN value
            END
        ) AS generic_significant_wave_height_m,

        MAX(
            CASE
                WHEN variable = 'VGTA'
                THEN value
            END
        ) AS generic_average_wave_period_s,

        COUNT(*) AS variable_count

    FROM source

    GROUP BY
        spot_id,
        platform_id,
        observation_time,
        latitude,
        longitude

)

SELECT *
FROM wave_conditions