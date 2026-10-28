-- Annual inflation from the monthly CPI (needs 12 months of history, so it starts a year after the series does).
select
    cur.month,
    round((cur.cpi_index / prev.cpi_index - 1) * 100, 2) as cpi_yoy,
    round((cur.trimmed_mean_index / prev.trimmed_mean_index - 1) * 100, 2) as trimmed_mean_yoy
from {{ ref('stg_cpi_monthly') }} cur
join {{ ref('stg_cpi_monthly') }} prev
  on prev.month = cur.month - interval 1 year
