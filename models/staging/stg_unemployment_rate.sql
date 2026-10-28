select period_start as month, value as unemployment_rate
from {{ ref('stg_observations') }}
where source_id = 'unemployment_rate'
