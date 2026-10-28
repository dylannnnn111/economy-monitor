-- One row per source per period, with a real date for the start of the period.
select
    source_id,
    period,
    {{ period_start('period') }} as period_start,
    case when period like '____-Q_' then 'Q' else 'M' end as frequency,
    value,
    unit,
    label,
    fetched_at
from {{ source('raw', 'observations') }}
