-- The handover from quarterly to monthly CPI only holds up if the two overlap somewhere.
select 'no overlap between quarterly and monthly CPI' as problem
where (select count(*) from {{ ref('int_cpi_quarterly_both') }} q
       join {{ ref('int_cpi_quarterly_both') }} m using (quarter)
       where q.method = 'quarterly CPI' and m.method = 'monthly CPI') = 0
