-- '2026-08' -> 2026-08-01, '2025-Q3' -> 2025-07-01
{% macro period_start(col) -%}
    case
        when {{ col }} like '____-Q_' then make_date(cast(left({{ col }}, 4) as integer), (cast(right({{ col }}, 1) as integer) - 1) * 3 + 1, 1)
        else cast({{ col }} || '-01' as date)
    end
{%- endmacro %}
