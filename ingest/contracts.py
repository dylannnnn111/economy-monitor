"""Check a fetched series against its source contract. Returns a list of problems (empty = pass)."""
import calendar
import re
from datetime import date

from .sources import Contract

MONTHLY = re.compile(r"^(\d{4})-(\d{2})$")
QUARTERLY = re.compile(r"^(\d{4})-Q([1-4])$")


def period_end(p: str) -> date:
    m = MONTHLY.match(p)
    if m:
        y, mo = int(m[1]), int(m[2])
        return date(y, mo, calendar.monthrange(y, mo)[1])
    m = QUARTERLY.match(p)
    if m:
        y, mo = int(m[1]), int(m[2]) * 3
        return date(y, mo, calendar.monthrange(y, mo)[1])
    raise ValueError(f"unrecognised period {p!r}")


def next_period(p: str) -> str:
    m = MONTHLY.match(p)
    if m:
        y, mo = int(m[1]), int(m[2])
        return f"{y + mo // 12}-{mo % 12 + 1:02d}"
    m = QUARTERLY.match(p)
    y, q = int(m[1]), int(m[2])
    return f"{y + q // 4}-Q{q % 4 + 1}"


def check(c: Contract, unit: str, points: list[tuple[str, float]], today: date) -> list[str]:
    problems: list[str] = []
    if len(points) < c.min_obs:
        problems.append(f"only {len(points)} observations (expected at least {c.min_obs})")
    if not points:
        return problems

    pattern = MONTHLY if c.frequency == "M" else QUARTERLY
    bad = [p for p, _ in points if not pattern.match(p)]
    if bad:
        problems.append(f"periods aren't {'monthly' if c.frequency == 'M' else 'quarterly'} (e.g. {bad[0]!r}) - frequency changed?")
        return problems

    if c.unit.lower() not in (unit or "").lower():
        problems.append(f"unit is {unit!r}, expected something containing {c.unit!r}")

    periods = [p for p, _ in points]
    if len(set(periods)) != len(periods):
        problems.append("duplicate periods")
    if periods != sorted(periods, key=period_end):
        problems.append("periods out of order")
    else:
        gaps = [f"{a} -> {b}" for a, b in zip(periods, periods[1:]) if next_period(a) != b]
        if gaps:
            problems.append(f"gaps in the series: {', '.join(gaps[:3])}")

    lo, hi = c.value_range
    out = [(p, v) for p, v in points if not lo <= v <= hi]
    if out:
        problems.append(f"{len(out)} values outside {lo}-{hi} (e.g. {out[0][0]} = {out[0][1]})")

    latest = periods[-1]
    if c.retired_after:
        if period_end(latest) > period_end(c.retired_after):
            problems.append(f"series was frozen at {c.retired_after} but now has {latest} - the source changed, review the mapping")
    elif c.max_age_days is not None:
        age = (today - period_end(latest)).days
        if age > c.max_age_days:
            problems.append(f"latest period {latest} ended {age} days ago (limit {c.max_age_days}) - stale or discontinued?")
    return problems
