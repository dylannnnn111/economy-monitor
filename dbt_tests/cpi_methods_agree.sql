-- Where both the quarterly CPI and the monthly CPI give an annual inflation figure for the same
-- quarter, they should agree within 0.3 points. If they don't, the monthly mapping has gone wrong.
select q.quarter, q.cpi_yoy as quarterly, m.cpi_yoy as from_monthly
from {{ ref('int_cpi_quarterly_both') }} q
join {{ ref('int_cpi_quarterly_both') }} m using (quarter)
where q.method = 'quarterly CPI' and m.method = 'monthly CPI'
  and abs(q.cpi_yoy - m.cpi_yoy) > 0.3
