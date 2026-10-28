select month, prev_month
from (select month, lag(month) over (order by month) as prev_month from {{ ref('fct_macro_monthly') }})
where prev_month is not null and month <> prev_month + interval 1 month
