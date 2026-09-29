{% test valid_angle(model, column_name) %}

SELECT *
FROM {{ model }}

WHERE {{ column_name }} < 0
   OR {{ column_name }} > 360

{% endtest %}