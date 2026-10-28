-- Cash rate target as at the end of each month (the current month is "so far").
select period_start as month, value as cash_rate_target
from {{ ref('stg_observations') }}
where source_id = 'cash_rate_target'
