"""Download and parse ABS and RBA data. Standard library only."""
import csv
import io
import re
import time
import urllib.error
import urllib.request

UA = "economy-monitor (+https://github.com/dylannnnn111/economy-monitor)"
ABS_BASE = "https://data.api.abs.gov.au/rest"


class SourceError(Exception):
    pass


def http_get(url: str, accept: str | None = None, tries: int = 3) -> str:
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    last: Exception | None = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return r.read().decode("utf-8-sig")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""  # ABS answers "no results" with a 404
            if e.code < 500:
                raise SourceError(f"{url} -> HTTP {e.code}") from e
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise SourceError(f"{url} failed after {tries} tries: {last}")


# ---------------------------------------------------------------- ABS (SDMX CSV)

def abs_url(dataflow: str, key: str, start: str) -> str:
    return f"{ABS_BASE}/data/{dataflow}/{key}?startPeriod={start}"


def _split(v: str) -> tuple[str, str]:
    """'3: Percentage change' -> ('3', 'Percentage change')"""
    i = v.find(": ")
    return (v, v) if i == -1 else (v[:i], v[i + 2:])


NON_DIM = {"DATAFLOW", "TIME_PERIOD", "OBS_VALUE", "UNIT_MEASURE", "UNIT_MULT", "OBS_STATUS", "OBS_COMMENT", "DECIMALS", "BASE_PERIOD", "FREQ"}


def parse_abs_csv(text: str) -> list[dict]:
    """Parse ABS SDMX-CSV (labels=both) into series: {dims, unit, points}."""
    if not text.strip():
        return []
    rows = list(csv.reader(io.StringIO(text)))
    header, body = rows[0], [r for r in rows[1:] if any(r)]
    ids = [h.split(":")[0].strip() for h in header]
    if "TIME_PERIOD" not in ids or "OBS_VALUE" not in ids:
        raise SourceError(f"ABS CSV is missing TIME_PERIOD/OBS_VALUE columns (got {ids})")
    groups: dict[str, dict] = {}
    for r in body:
        rec = dict(zip(ids, r))
        dims = {k: _split(v) for k, v in rec.items() if k not in NON_DIM and v}
        key = ".".join(c for c, _ in dims.values())
        g = groups.setdefault(key, {"dims": dims, "unit": _split(rec.get("UNIT_MEASURE", ""))[1], "points": []})
        try:
            value = float(rec["OBS_VALUE"])
        except ValueError:
            continue
        g["points"].append((rec["TIME_PERIOD"].strip(), value))
    # The live ABS API doesn't promise rows in time order (the first live run on GitHub
    # Actions got them shuffled), so sort here. Periods like 2026-08 and 2026-Q3 sort as text.
    for g in groups.values():
        g["points"].sort(key=lambda pv: pv[0])
    return list(groups.values())


def pick_series(series: list[dict], prefer: dict) -> list[dict]:
    """When a key matches several series (e.g. original and seasonally adjusted), keep the preferred one."""
    out = series
    for dim, codes in prefer.items():
        for code in codes:
            hit = [s for s in out if s["dims"].get(dim, ("",))[0] == code]
            if hit:
                out = hit
                break
    return out


def abs_latest_version(dataflow_id: str) -> str | None:
    xml = http_get(f"{ABS_BASE}/dataflow/ABS/{dataflow_id}/latest", accept="application/vnd.sdmx.structure+xml;version=2.1")
    m = re.search(r'<structure:Dataflow[^>]*\bversion="([^"]+)"', xml) or re.search(r'\bversion="(\d+\.\d+\.\d+)"', xml)
    return m.group(1) if m else None


# ---------------------------------------------------------------- RBA (CSV tables)

MONTHS = {m: f"{i:02d}" for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_rba_date(s: str) -> str | None:
    """RBA uses '31/08/2026' in some tables and '02-Oct-2026' in others."""
    s = s.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", s)
    if m and m[2].title() in MONTHS:
        return f"{m[3]}-{MONTHS[m[2].title()]}-{int(m[1]):02d}"
    return None


def rba_url(table: str) -> str:
    return f"https://www.rba.gov.au/statistics/tables/csv/{table.lower()}-data.csv"


def parse_rba_csv(text: str, series_id: str) -> dict:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    meta = {r[0].strip(): r[1:] for r in rows if r and r[0].strip() in {"Title", "Units", "Frequency", "Series ID"}}
    if "Series ID" not in meta:
        raise SourceError("RBA table doesn't have the expected layout (no 'Series ID' row)")
    ids = [x.strip() for x in meta["Series ID"]]
    if series_id not in ids:
        raise SourceError(f"RBA series {series_id} is no longer in the table (has {', '.join(i for i in ids if i)})")
    i = ids.index(series_id)
    points = []
    for r in rows:
        d = parse_rba_date(r[0]) if r else None
        if d and len(r) > i + 1 and r[i + 1].strip():
            points.append((d, float(r[i + 1])))
    return {"title": meta.get("Title", [""] * (i + 1))[i], "unit": meta.get("Units", [""] * (i + 1))[i], "points": points}
