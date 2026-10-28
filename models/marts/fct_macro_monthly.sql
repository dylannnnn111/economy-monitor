-- One row per month: inflation, the cash rate, unemployment and dwelling approvals side by side.
-- Before the monthly CPI has a year of history, inflation comes from the quarterly CPI for that quarter.
-- Headline CPI lines up across the switch (tested in cpi_methods_agree). The trimmed mean doesn't: the
-- ABS calculates it differently for monthly and quarterly data, so inflation_source marks the break.
with spine as (
    select unnest(generate_series(
        (select min(month) from {{ ref('stg_unemployment_rate') }}),
        (select max(m) from (
            select max(month) as m from {{ ref('stg_unemployment_rate') }}
            union all select max(month) from {{ ref('stg_cash_rate') }}
            union all select max(month) from {{ ref('stg_cpi_monthly') }}
            union all select max(month) from {{ ref('stg_dwelling_approvals') }}
        )),
        interval 1 month
    ))::date as month
),
approvals as (
    select month, dwellings_approved,
           case when count(*) over w = 12 then sum(dwellings_approved) over w end as dwellings_approved_12m
    from {{ ref('stg_dwelling_approvals') }}
    window w as (order by month rows between 11 preceding and current row)
)
select
    s.month,
    strftime(s.month, '%Y-%m') as month_label,
    coalesce(m.cpi_yoy, q.cpi_yoy) as inflation,
    coalesce(m.trimmed_mean_yoy, q.trimmed_mean_yoy) as trimmed_mean_inflation,
    case when m.cpi_yoy is not null then 'monthly CPI'
         when q.cpi_yoy is not null then 'quarterly CPI'
    end as inflation_source,
    r.cash_rate,
    round(r.cash_rate - coalesce(m.trimmed_mean_yoy, q.trimmed_mean_yoy), 2) as real_cash_rate,
    round(u.unemployment_rate, 2) as unemployment_rate,
    a.dwellings_approved,
    a.dwellings_approved_12m
from spine s
left join {{ ref('int_cpi_monthly_yoy') }} m on m.month = s.month
left join {{ ref('int_cpi_quarterly') }} q on q.quarter = date_trunc('quarter', s.month)
left join {{ ref('stg_cash_rate') }} r on r.month = s.month
left join {{ ref('stg_unemployment_rate') }} u on u.month = s.month
left join approvals a on a.month = s.month
order by s.month
