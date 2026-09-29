SELECT *
FROM {{ ref('int_copernicus_wave_conditions') }}

WHERE
       significant_wave_height_m < 0
    OR peak_wave_period_s <= 0
    OR mean_wave_direction_deg < 0
    OR mean_wave_direction_deg > 360
    OR mean_wave_period_s <= 0
    OR average_upper_third_wave_height_m < 0
    OR average_upper_third_wave_period_s <= 0
    OR maximum_wave_height_zero_crossing_m < 0
    OR estimated_maximum_wave_height_m < 0
    OR generic_significant_wave_height_m < 0
    OR generic_average_wave_period_s <= 0