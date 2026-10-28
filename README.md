# Aussie Economy Monitor

A small, modern data stack for the Australian economy. It pulls ABS and RBA data every morning, checks each source against a contract, models it with dbt in DuckDB, tests it, and exports one JSON file for the dashboard on [dylanlewis.au](https://dylanlewis.au).

[![ci](https://github.com/dylannnnn111/economy-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/dylannnnn111/economy-monitor/actions/workflows/ci.yml)

```
ABS Data API ─┐                          ┌─ staging ─ intermediate ─ marts ─┐
              ├─ ingest (contracts) ─ DuckDB ────────── dbt build ──────────┼─ export ─ out/economy-monitor.json ─ site
RBA tables ───┘                          └──────── 29 data tests ───────────┘
```

## What it answers

- **Are wages beating prices?** Wage Price Index growth against CPI inflation, quarter by quarter, and the real wage growth that leaves.
- **Where is inflation against the cash rate?** Headline and trimmed mean inflation, the cash rate, and the real cash rate.
- **Jobs and building:** the unemployment rate, and dwelling approvals over the last 12 months.

## Sources

| id | What | Where |
|---|---|---|
| `cpi_monthly_all_groups` | CPI, all groups, monthly index | ABS `CPI` 2.0.0 |
| `cpi_monthly_trimmed_mean` | CPI, trimmed mean, monthly index | ABS `CPI` 2.0.0 |
| `cpi_quarterly_all_groups` | CPI, all groups, quarterly (ended Sep 2025) | ABS `CPI` 1.1.0 |
| `cpi_quarterly_trimmed_mean` | CPI, trimmed mean, quarterly (ended Sep 2025) | ABS `CPI` 1.1.0 |
| `unemployment_rate` | Unemployment rate, seasonally adjusted | ABS `LF` |
| `wpi` | Wage Price Index, total hourly rates excl. bonuses | ABS `WPI` |
| `dwelling_approvals` | Dwelling units approved, total residential | ABS `BA_GCCSA` |
| `cash_rate` | Cash rate target, monthly average | RBA table F1.1 |

## Source contracts

Every source has a contract in [`ingest/sources.py`](ingest/sources.py): expected frequency, unit, minimum history, value range, and how old the latest period may be. Ingestion checks every source and loads only the ones that pass. If any fail, the run exits non-zero and the refresh workflow opens a `data-contract` issue listing each problem.

The case this was built for really happened: in 2025 the ABS moved CPI to monthly and froze the quarterly dataflow at the Sep quarter. A pipeline reading quarterly CPI would have gone quietly stale. Here the quarterly sources are marked `retired_after: 2025-Q3`, the monthly CPI is pinned to dataflow version 2.0.0 (a newer version fails the run), and any series that goes stale or comes back fails loudly.

## Joining quarterly and monthly CPI

Index levels use different bases, so the two CPI series are never spliced. Each is turned into annual inflation by comparing it with itself a year earlier. The monthly series is averaged to quarters (complete quarters only). Where both exist (Jun and Sep quarters 2025), headline inflation agrees within 0.03 points, and `dbt_tests/cpi_methods_agree.sql` fails the build if they ever drift more than 0.3 apart.

The trimmed mean doesn't line up the same way, because the ABS calculates it differently for monthly and quarterly data. `inflation_source` marks the switch in the marts.

## Run it

```
pip install -r requirements.txt
python -m ingest --live                        # or --snapshot data/snapshot.json to run offline
dbt build --profiles-dir .
python scripts/export.py                       # writes out/economy-monitor.json
python -m unittest discover tests              # 20 tests
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .   # lineage graph and model docs
```

`data/snapshot.json` is a real pull from 28 Oct 2026 (via [aussie-data-mcp](https://github.com/dylannnnn111/aussie-data-mcp)), used by CI so tests don't depend on ABS being up.

## Models

- `staging`: one view per source, with periods turned into dates
- `intermediate`: annual CPI inflation by quarter (both methods, then one per quarter) and by month
- `marts`: `fct_macro_monthly`, `fct_real_wages_quarterly`, `fct_headline`

## Schedule

`.github/workflows/refresh.yml` runs daily at 21:23 UTC (early morning in Sydney): ingest live, `dbt build`, `dbt source freshness`, export, and commit `out/` if the data changed.

Data: Australian Bureau of Statistics and Reserve Bank of Australia, CC BY 4.0.
