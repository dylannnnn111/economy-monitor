select period_start as month, value as cash_rate
from {{ ref('stg_observations') }}
where source_id = 'cash_rate'
