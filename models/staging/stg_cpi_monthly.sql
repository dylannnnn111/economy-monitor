select
    period_start as month,
    max(case when source_id = 'cpi_monthly_all_groups' then value end) as cpi_index,
    max(case when source_id = 'cpi_monthly_trimmed_mean' then value end) as trimmed_mean_index
from {{ ref('stg_observations') }}
where source_id in ('cpi_monthly_all_groups', 'cpi_monthly_trimmed_mean')
group by 1
