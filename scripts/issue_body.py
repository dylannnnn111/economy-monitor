"""Markdown body for the refresh-failure issue: one line per source that broke its contract."""
import json
import sys
from pathlib import Path

run_url = sys.argv[1] if len(sys.argv) > 1 else ""
lines = [f"Refresh failed. Run: {run_url}", ""]
report = Path("out/contracts.json")
if report.exists():
    bad = [s for s in json.loads(report.read_text())["sources"] if s["problems"]]
    lines += [f"- **{s['id']}**: {'; '.join(s['problems'])}" for s in bad] or \
             ["All source contracts passed - the failure is in dbt (a model or test) or the export."]
else:
    lines.append("Ingestion didn't get far enough to write a contract report.")
print("\n".join(lines))
