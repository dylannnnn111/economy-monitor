"""Unit tests for parsing and contracts. Run with: python -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ingest import fetch
from ingest.contracts import check, next_period, period_end
from ingest.sources import SOURCES, Contract

ROOT = Path(__file__).resolve().parents[1]

ABS_CSV = """DATAFLOW,MEASURE: Measure,INDEX: Index,TSEST: Adjustment Type,REGION: Region,FREQ: Frequency,TIME_PERIOD: Time Period,OBS_VALUE,UNIT_MEASURE: Unit of Measure
ABS:CPI(2.0.0),1: Index Numbers,10001: All groups CPI,10: Original,50: Weighted average of eight capital cities,M: Monthly,2026-07,103.07,IN: Index Numbers
ABS:CPI(2.0.0),1: Index Numbers,10001: All groups CPI,10: Original,50: Weighted average of eight capital cities,M: Monthly,2026-08,103.5,IN: Index Numbers
ABS:CPI(2.0.0),1: Index Numbers,10001: All groups CPI,20: Seasonally Adjusted,50: Weighted average of eight capital cities,M: Monthly,2026-07,102.9,IN: Index Numbers
ABS:CPI(2.0.0),1: Index Numbers,10001: All groups CPI,20: Seasonally Adjusted,50: Weighted average of eight capital cities,M: Monthly,2026-08,103.2,IN: Index Numbers
"""

RBA_CSV = "﻿" + """F1.1 INTEREST RATES AND YIELDS - MONEY MARKET,,
Title,Cash Rate Target,Interbank Overnight Cash Rate
Description,Cash Rate Target; monthly average,Interbank Overnight Cash Rate
Frequency,Monthly,Monthly
Type,Original,Original
Units,Per cent,Per cent
,,
,,
Source,RBA,RBA
Publication date,01-Oct-2026,01-Oct-2026
Series ID,FIRMMCRT,FIRMMCRI
31-Aug-2026,4.35,4.34
30/09/2026,4.36,4.35
"""

MONTHLY = Contract("M", "index", 2, 75, (50, 300))


def months(start: str, n: int, value=100.0):
    out, p = [], start
    for _ in range(n):
        out.append((p, value))
        p = next_period(p)
    return out


class Parsing(unittest.TestCase):
    def test_abs_groups_series_and_reads_units(self):
        series = fetch.parse_abs_csv(ABS_CSV)
        self.assertEqual(len(series), 2)
        self.assertEqual(series[0]["unit"], "Index Numbers")
        self.assertEqual(series[0]["points"], [("2026-07", 103.07), ("2026-08", 103.5)])

    def test_abs_points_come_back_in_time_order(self):
        head, *rows = ABS_CSV.strip().split("\n")
        shuffled = "\n".join([head] + rows[::-1]) + "\n"
        for s in fetch.parse_abs_csv(shuffled):
            self.assertEqual([p for p, _ in s["points"]], ["2026-07", "2026-08"])

    def test_abs_prefer_picks_one_adjustment(self):
        picked = fetch.pick_series(fetch.parse_abs_csv(ABS_CSV), {"TSEST": ["20", "10"]})
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0]["dims"]["TSEST"][0], "20")

    def test_abs_empty_response_is_no_series(self):
        self.assertEqual(fetch.parse_abs_csv(""), [])

    def test_abs_missing_columns_fails_loudly(self):
        with self.assertRaises(fetch.SourceError):
            fetch.parse_abs_csv("DATAFLOW,FOO\nx,y\n")

    def test_rba_both_date_formats_and_bom(self):
        t = fetch.parse_rba_csv(RBA_CSV, "FIRMMCRT")
        self.assertEqual(t["unit"], "Per cent")
        self.assertEqual(t["points"], [("2026-08-31", 4.35), ("2026-09-30", 4.36)])

    def test_rba_missing_series_fails_loudly(self):
        with self.assertRaises(fetch.SourceError):
            fetch.parse_rba_csv(RBA_CSV, "FIRMMCRTD")


class Versions(unittest.TestCase):
    def test_reads_dataflow_version_from_structure_xml(self):
        xml = '<message:Structure><structure:Dataflows><structure:Dataflow id="CPI" agencyID="ABS" version="2.0.0" isFinal="true"><common:Name>CPI</common:Name></structure:Dataflow></structure:Dataflows></message:Structure>'
        orig = fetch.http_get
        fetch.http_get = lambda url, accept=None: xml
        try:
            self.assertEqual(fetch.abs_latest_version("CPI"), "2.0.0")
        finally:
            fetch.http_get = orig


class MonthEnd(unittest.TestCase):
    def test_daily_series_keeps_last_value_in_each_month(self):
        from ingest import __main__ as run
        from ingest.sources import BY_ID
        daily = "\n".join([
            "Title,Cash Rate Target", "Units,Per cent", "Frequency,Daily", "Series ID,FIRMMCRTD",
            "29-Sep-2026,4.35", "30-Sep-2026,4.60", "01-Oct-2026,4.60",
        ])
        orig = fetch.http_get
        fetch.http_get = lambda url, accept=None: daily
        try:
            unit, pts, _, _ = run.fetch_live(BY_ID["cash_rate_target"])
        finally:
            fetch.http_get = orig
        self.assertEqual(unit, "Per cent")
        self.assertEqual(pts, [("2026-09", 4.6), ("2026-10", 4.6)])


class Periods(unittest.TestCase):
    def test_next_period_rolls_years(self):
        self.assertEqual(next_period("2025-12"), "2026-01")
        self.assertEqual(next_period("2025-Q4"), "2026-Q1")

    def test_period_end(self):
        self.assertEqual(period_end("2024-02"), date(2024, 2, 29))
        self.assertEqual(period_end("2025-Q3"), date(2025, 9, 30))


class Contracts(unittest.TestCase):
    today = date(2026, 10, 28)

    def test_clean_series_passes(self):
        self.assertEqual(check(MONTHLY, "Index Numbers", months("2026-01", 8), self.today), [])

    def test_stale_series_fails(self):
        problems = check(MONTHLY, "Index Numbers", months("2025-01", 6), self.today)
        self.assertTrue(any("stale" in p for p in problems), problems)

    def test_gap_fails(self):
        pts = months("2026-01", 8)
        del pts[3]
        self.assertTrue(any("gaps" in p for p in check(MONTHLY, "Index Numbers", pts, self.today)))

    def test_unit_change_fails(self):
        self.assertTrue(any("unit" in p for p in check(MONTHLY, "Percent", months("2026-01", 8), self.today)))

    def test_frequency_change_fails(self):
        pts = [("2026-Q1", 100.0), ("2026-Q2", 101.0)]
        self.assertTrue(any("frequency" in p for p in check(MONTHLY, "Index Numbers", pts, self.today)))

    def test_out_of_range_fails(self):
        pts = months("2026-01", 8)
        pts[-1] = (pts[-1][0], 9999.0)
        self.assertTrue(any("outside" in p for p in check(MONTHLY, "Index Numbers", pts, self.today)))

    def test_duplicates_fail(self):
        pts = months("2026-01", 8) + [("2026-08", 100.0)]
        self.assertTrue(any("duplicate" in p for p in check(MONTHLY, "Index Numbers", pts, self.today)))

    def test_retired_series_coming_back_fails(self):
        retired = Contract("Q", "index", 2, None, (50, 300), retired_after="2025-Q3")
        ok = [("2025-Q2", 100.0), ("2025-Q3", 101.0)]
        self.assertEqual(check(retired, "Index Numbers", ok, self.today), [])
        back = ok + [("2025-Q4", 102.0)]
        self.assertTrue(any("frozen" in p for p in check(retired, "Index Numbers", back, self.today)))

    def test_too_few_observations_fails(self):
        self.assertTrue(any("observations" in p for p in check(MONTHLY, "Index Numbers", months("2026-09", 1), self.today)))


class Snapshot(unittest.TestCase):
    def test_snapshot_covers_every_source_and_passes(self):
        snap = json.loads((ROOT / "data" / "snapshot.json").read_text())
        self.assertEqual(set(snap["sources"]), {s.id for s in SOURCES})
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "EM_DB": f"{d}/t.duckdb", "EM_REPORT": f"{d}/r.json"}
            r = subprocess.run([sys.executable, "-m", "ingest", "--snapshot", "data/snapshot.json"],
                               cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            report = json.loads(Path(f"{d}/r.json").read_text())
            self.assertTrue(all(s["status"] == "pass" for s in report["sources"]))

    def test_broken_source_is_reported_and_not_loaded(self):
        snap = json.loads((ROOT / "data" / "snapshot.json").read_text())
        snap["units"]["unemployment_rate"] = "Thousands"  # simulate ABS changing the measure
        with tempfile.TemporaryDirectory() as d:
            Path(f"{d}/s.json").write_text(json.dumps(snap))
            env = {**os.environ, "EM_DB": f"{d}/t.duckdb", "EM_REPORT": f"{d}/r.json"}
            r = subprocess.run([sys.executable, "-m", "ingest", "--snapshot", f"{d}/s.json"],
                               cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            report = {s["id"]: s for s in json.loads(Path(f"{d}/r.json").read_text())["sources"]}
            self.assertEqual(report["unemployment_rate"]["status"], "fail")
            self.assertEqual(report["cash_rate"]["status"], "pass")
            import duckdb
            n = duckdb.connect(f"{d}/t.duckdb").execute(
                "select count(*) from raw.observations where source_id = 'unemployment_rate'").fetchone()[0]
            self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
