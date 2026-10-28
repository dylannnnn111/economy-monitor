"""Every series the monitor pulls, and the contract it has to meet.

A contract is what we expect a source to look like. If ABS or the RBA changes a
dataflow (new version, different unit, a series stops updating), ingestion stops
with a clear message instead of quietly feeding bad numbers into the models.
The real example: ABS moved CPI to monthly in 2025 and froze the quarterly
dataflow at the Sep quarter 2025.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Contract:
    frequency: str                    # "M" or "Q"
    unit: str                         # text the published unit must contain (case-insensitive)
    min_obs: int                      # fewest observations we accept
    max_age_days: int | None          # latest period END may be at most this old; None = no check
    value_range: tuple[float, float]  # every value must sit inside this
    retired_after: str | None = None  # series is frozen; a newer period means the source changed
    dataflow_version: str | None = None  # ABS dataflow version we mapped against


@dataclass(frozen=True)
class Source:
    id: str
    kind: str          # "abs" or "rba"
    label: str
    contract: Contract
    # ABS
    dataflow: str = ""
    key: str = ""
    prefer: dict = field(default_factory=dict)  # dimension -> codes in order of preference, when a key matches several series
    # RBA
    table: str = ""
    series_id: str = ""
    month_end: bool = False  # daily series: keep the last observation in each month
    start: str = "2015-01"


SOURCES: list[Source] = [
    Source(
        id="cpi_monthly_all_groups", kind="abs", label="CPI, all groups, Australia (monthly index)",
        dataflow="ABS,CPI,2.0.0", key="1.10001..50.M", prefer={"TSEST": ["10", "20"]},
        contract=Contract("M", "index", 12, 75, (50, 300), dataflow_version="2.0.0"),
    ),
    Source(
        id="cpi_monthly_trimmed_mean", kind="abs", label="CPI, trimmed mean, Australia (monthly index)",
        dataflow="ABS,CPI,2.0.0", key="1.999902..50.M", prefer={"TSEST": ["20", "10"]},
        contract=Contract("M", "index", 12, 75, (50, 300), dataflow_version="2.0.0"),
    ),
    Source(
        id="cpi_quarterly_all_groups", kind="abs", label="CPI, all groups, Australia (quarterly index, ended Sep 2025)",
        dataflow="ABS,CPI,1.1.0", key="1.10001.10.50.Q",
        contract=Contract("Q", "index", 20, None, (50, 300), retired_after="2025-Q3", dataflow_version="1.1.0"),
    ),
    Source(
        id="cpi_quarterly_trimmed_mean", kind="abs", label="CPI, trimmed mean, Australia (quarterly index, ended Sep 2025)",
        dataflow="ABS,CPI,1.1.0", key="1.999902.20.50.Q",
        contract=Contract("Q", "index", 20, None, (50, 300), retired_after="2025-Q3", dataflow_version="1.1.0"),
    ),
    Source(
        id="unemployment_rate", kind="abs", label="Unemployment rate, persons, seasonally adjusted, Australia",
        dataflow="ABS,LF", key="M13.3.1599.20.AUS.M",
        contract=Contract("M", "percent", 60, 60, (0, 20)),
    ),
    Source(
        id="wpi", kind="abs", label="Wage Price Index, total hourly rates excl. bonuses, all sectors, seasonally adjusted",
        dataflow="ABS,WPI", key="1.THRPEB.7.TOT.20.AUS.Q",
        contract=Contract("Q", "index", 20, 150, (50, 400)),
    ),
    Source(
        id="dwelling_approvals", kind="abs", label="Dwelling units approved, total residential, Australia (original)",
        dataflow="ABS,BA_GCCSA", key="1.1.9.TOT.100.10.AUS.M",
        contract=Contract("M", "number", 60, 75, (1_000, 60_000)),
    ),
    Source(
        id="cash_rate", kind="rba", label="RBA cash rate target (monthly average)",
        table="f1.1", series_id="FIRMMCRT",
        contract=Contract("M", "per cent", 60, 45, (0, 20)),
    ),
    Source(
        id="cash_rate_target", kind="rba", label="RBA cash rate target (end of month, from the daily table)",
        table="f1", series_id="FIRMMCRTD", month_end=True,
        # A monthly average hides a change made late in the month (the 30 Sep 2026 hike shows as +0.01),
        # so the headline uses the target as at the end of each month.
        contract=Contract("M", "per cent", 60, 45, (0, 20)),
    ),
]

BY_ID = {s.id: s for s in SOURCES}
