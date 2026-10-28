select period_start as quarter, value as wpi_index
from {{ ref('stg_observations') }}
where source_id = 'wpi'
