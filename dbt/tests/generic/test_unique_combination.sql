{# Package-free composite-key uniqueness test.
   Usage in schema.yml:
     tests:
       - unique_combination:
           columns: ['region_key', 'period_utc']  #}
{% test unique_combination(model, columns) %}

select
    {{ columns | join(', ') }},
    count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
