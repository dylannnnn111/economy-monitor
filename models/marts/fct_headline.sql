-- The latest reading of each measure, with the period it's for. Feeds the dashboard's headline tiles.
with m as (select * from {{ ref('fct_macro_monthly') }}),
latest as (
    select 'inflation' as measure, 'Annual CPI inflation' as label, '%' as unit,
           arg_max(inflation, month) filter (where inflation is not null) as value,
           max(month) filter (where inflation is not null) as as_of from m
    union all
    select 'trimmed_mean_inflation', 'Trimmed mean inflation (RBA''s preferred)', '%',
           arg_max(trimmed_mean_inflation, month) filter (where trimmed_mean_inflation is not null),
           max(month) filter (where trimmed_mean_inflation is not null) from m
    union all
    select 'cash_rate', 'Cash rate target', '%',
           arg_max(cash_rate_target, month) filter (where cash_rate_target is not null),
           max(month) filter (where cash_rate_target is not null) from m
    union all
    select 'unemployment_rate', 'Unemployment rate', '%',
           arg_max(unemployment_rate, month) filter (where unemployment_rate is not null),
           max(month) filter (where unemployment_rate is not null) from m
    union all
    select 'dwellings_approved_12m', 'Dwellings approved, last 12 months', 'dwellings',
           arg_max(dwellings_approved_12m, month) filter (where dwellings_approved_12m is not null),
           max(month) filter (where dwellings_approved_12m is not null) from m
    union all
    select 'real_wage_growth', 'Real wage growth (wages minus prices)', '%',
           arg_max(real_wage_growth, quarter), max(quarter) from {{ ref('fct_real_wages_quarterly') }}
)
select measure, label, unit, round(value, 2) as value, as_of from latest
