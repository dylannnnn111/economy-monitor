-- One annual inflation figure per quarter: the published quarterly CPI while it lasted, then the monthly CPI.
select quarter, cpi_yoy, trimmed_mean_yoy, method
from {{ ref('int_cpi_quarterly_both') }}
qualify row_number() over (
    partition by quarter
    order by case method when 'quarterly CPI' then 1 else 2 end
) = 1
