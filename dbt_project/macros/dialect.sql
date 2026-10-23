{% macro date_diff_compat(part, start, end) -%}
    {{ return(adapter.dispatch('date_diff_compat', 'breakout')(part, start, end)) }}
{%- endmacro %}

{% macro default__date_diff_compat(part, start, end) -%}
    date_diff('{{ part }}', {{ start }}, {{ end }})
{%- endmacro %}

{% macro snowflake__date_diff_compat(part, start, end) -%}
    datediff('{{ part }}', {{ start }}, {{ end }})
{%- endmacro %}

{% macro regexp_matches_compat(expression, pattern) -%}
    {{ return(adapter.dispatch('regexp_matches_compat', 'breakout')(expression, pattern)) }}
{%- endmacro %}

{% macro default__regexp_matches_compat(expression, pattern) -%}
    regexp_matches({{ expression }}, {{ pattern }})
{%- endmacro %}

{% macro snowflake__regexp_matches_compat(expression, pattern) -%}
    regexp_like({{ expression }}, {{ pattern }})
{%- endmacro %}
