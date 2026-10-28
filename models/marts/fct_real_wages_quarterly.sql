-- Are wages beating prices? Annual wage growth (WPI) against annual inflation (CPI), by quarter.
-- Real wage growth = (1 + wage growth) / (1 + inflation) - 1.
with wages as (
    select cur.quarter,
           round((cur.wpi_index / prev.wpi_index - 1) * 100, 2) as wage_growth
    from {{ ref('stg_wpi') }} cur
    join {{ ref('stg_wpi') }} prev on prev.quarter = cur.quarter - interval 1 year
)
select
    w.quarter,
    strftime(w.quarter, '%Y') || '-Q' || cast(quarter(w.quarter) as varchar) as quarter_label,
    w.wage_growth,
    c.cpi_yoy as inflation,
    round(((1 + w.wage_growth / 100) / (1 + c.cpi_yoy / 100) - 1) * 100, 2) as real_wage_growth,
    c.method as inflation_source
from wages w
join {{ ref('int_cpi_quarterly') }} c using (quarter)
order by w.quarter
