{% test unique_combination_of_columns(model, combination_of_columns) %}

SELECT
    {% for column_name in combination_of_columns %}
    {{ column_name }}{% if not loop.last %}, {% endif %}
    {% endfor %},
    COUNT(*) AS row_count

FROM {{ model }}

GROUP BY
    {% for column_name in combination_of_columns %}
    {{ column_name }}{% if not loop.last %}, {% endif %}
    {% endfor %}

HAVING COUNT(*) > 1

{% endtest %}
