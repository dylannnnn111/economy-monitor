select period_start as month, value as dwellings_approved
from {{ ref('stg_observations') }}
where source_id = 'dwelling_approvals'
