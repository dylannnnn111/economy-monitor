-- ABS stopped the quarterly CPI at the Sep quarter 2025. Kept for history.
select
    period_start as quarter,
    max(case when source_id = 'cpi_quarterly_all_groups' then value end) as cpi_index,
    max(case when source_id = 'cpi_quarterly_trimmed_mean' then value end) as trimmed_mean_index
from {{ ref('stg_observations') }}
where source_id in ('cpi_quarterly_all_groups', 'cpi_quarterly_trimmed_mean')
group by 1
