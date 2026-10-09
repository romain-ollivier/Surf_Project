SELECT * FROM {{ ref('fct_surf_daily') }}
WHERE excellent_hours + very_good_hours + good_hours + fair_hours + poor_hours
    <> scored_hours
OR surf_index_min > surf_index_avg
OR surf_index_avg > surf_index_max
