"""Pull every source, check its contract, load it into DuckDB.

    python -m ingest --live                         # fetch from ABS and the RBA
    python -m ingest --snapshot data/snapshot.json  # load the saved snapshot (offline, used by CI)

Exits non-zero if any source breaks its contract. Every source is still checked so
one run reports every problem. Sources that pass are loaded; a failing source
keeps its previous data in the warehouse.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from . import fetch
from .contracts import check
from .sources import SOURCES, Source

DB = Path(os.environ.get("EM_DB", "warehouse/economy.duckdb"))
REPORT = Path(os.environ.get("EM_REPORT", "out/contracts.json"))

SCHEMA = """
create schema if not exists raw;
create table if not exists raw.observations (
    source_id varchar, period varchar, value double, unit varchar, label varchar, fetched_at timestamp
);
create table if not exists raw.load_log (
    source_id varchar, fetched_at timestamp, mode varchar, rows integer, url varchar, status varchar, problems varchar
);
"""


def to_month(p: str) -> str:
    """RBA monthly series are dated at month end (2026-09-30) - store as 2026-09."""
    return p[:7] if len(p) == 10 else p


def fetch_live(s: Source) -> tuple[str, list[tuple[str, float]], str, list[str]]:
    extra: list[str] = []
    if s.kind == "abs":
        url = fetch.abs_url(s.dataflow, s.key, s.start)
        series = fetch.pick_series(fetch.parse_abs_csv(fetch.http_get(url, accept="application/vnd.sdmx.data+csv;labels=both")), s.prefer)
        if len(series) != 1:
            return "", [], url, [f"key matched {len(series)} series (expected exactly 1) - dimensions changed?"]
        ver = s.contract.dataflow_version
        if ver and not s.contract.retired_after:
            latest = fetch.abs_latest_version(s.dataflow.split(",")[1])
            if latest and latest != ver:
                extra.append(f"ABS now publishes {s.dataflow.split(',')[1]} version {latest}; this pipeline was mapped to {ver} - review the key")
        return series[0]["unit"], series[0]["points"], url, extra
    url = fetch.rba_url(s.table)
    t = fetch.parse_rba_csv(fetch.http_get(url), s.series_id)
    pts = [(p, v) for p, v in t["points"] if p >= s.start]
    if s.month_end:
        last: dict[str, float] = {}
        for p, v in pts:  # points are in date order, so the last write per month wins
            last[p[:7]] = v
        return t["unit"], list(last.items()), url, extra
    return t["unit"], [(to_month(p), v) for p, v in pts], url, extra


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ingest")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true")
    g.add_argument("--snapshot", type=Path)
    a = ap.parse_args(argv)

    snap = json.loads(a.snapshot.read_text()) if a.snapshot else None
    today = date.fromisoformat(snap["pulled"]) if snap else date.today()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute(SCHEMA)

    report = {"run_at": now.isoformat(timespec="seconds") + "Z", "mode": "snapshot" if snap else "live", "as_of": today.isoformat(), "sources": []}
    failed = 0
    for s in SOURCES:
        try:
            if snap:
                if s.id not in snap["sources"]:
                    unit, pts, url, extra = "", [], str(a.snapshot), ["not in the snapshot"]
                else:
                    unit = snap["units"][s.id]
                    pts = [(to_month(p), float(v)) for p, v in snap["sources"][s.id]]
                    url, extra = str(a.snapshot), []
            else:
                unit, pts, url, extra = fetch_live(s)
            problems = extra + check(s.contract, unit, pts, today)
        except Exception as e:  # network or layout failure counts as a broken contract
            unit, pts, url, problems = "", [], "", [f"{type(e).__name__}: {e}"]

        status = "fail" if problems else "pass"
        if problems:
            failed += 1
        else:
            con.execute("delete from raw.observations where source_id = ?", [s.id])
            con.executemany(
                "insert into raw.observations values (?, ?, ?, ?, ?, ?)",
                [(s.id, p, v, unit, s.label, now) for p, v in pts],
            )
        con.execute("insert into raw.load_log values (?, ?, ?, ?, ?, ?, ?)",
                    [s.id, now, report["mode"], len(pts), url, status, "; ".join(problems)])
        report["sources"].append({"id": s.id, "label": s.label, "status": status, "rows": len(pts),
                                  "latest": pts[-1][0] if pts else None, "problems": problems})
        mark = "ok  " if not problems else "FAIL"
        print(f"{mark} {s.id:28} {len(pts):4} rows  latest {pts[-1][0] if pts else '-':8}  {'; '.join(problems)}")

    con.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2))
    if failed:
        print(f"\n{failed} source(s) broke their contract - see {REPORT}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
