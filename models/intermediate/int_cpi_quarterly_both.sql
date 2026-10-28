-- Annual CPI inflation by quarter, worked out two ways:
--   'quarterly CPI'  - from the published quarterly index (ends Sep quarter 2025)
--   'monthly CPI'    - from the average of the three monthly index values in the quarter
-- Index bases differ between the two, so each is compared only with itself a year earlier.
with published as (
    select quarter, cpi_index, trimmed_mean_index, 'quarterly CPI' as method
    from {{ ref('stg_cpi_quarterly') }}
),
from_monthly as (
    select date_trunc('quarter', month) as quarter,
           avg(cpi_index) as cpi_index,
           avg(trimmed_mean_index) as trimmed_mean_index,
           'monthly CPI' as method
    from {{ ref('stg_cpi_monthly') }}
    group by 1
    having count(*) = 3   -- complete quarters only
),
both_methods as (
    select * from published
    union all
    select * from from_monthly
)
select
    cur.quarter,
    cur.method,
    round((cur.cpi_index / prev.cpi_index - 1) * 100, 2) as cpi_yoy,
    round((cur.trimmed_mean_index / prev.trimmed_mean_index - 1) * 100, 2) as trimmed_mean_yoy
from both_methods cur
join both_methods prev
  on prev.method = cur.method
 and prev.quarter = cur.quarter - interval 1 year
