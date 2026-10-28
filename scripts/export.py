"""Export the marts, the contract report and the dbt lineage to one JSON file for the site.

    python scripts/export.py   # after `dbt build`; writes out/economy-monitor.json
"""
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("EM_DB", ROOT / "warehouse/economy.duckdb"))
OUT = ROOT / "out" / "economy-monitor.json"


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        rec = {}
        for c, v in zip(cols, r):
            rec[c] = v.isoformat()[:10] if isinstance(v, (date, datetime)) else v
        out.append(rec)
    return out


def lineage():
    """Model-to-model edges from dbt's manifest, for the lineage diagram."""
    m = json.loads((ROOT / "target" / "manifest.json").read_text())
    nodes, edges = [], []
    for uid, n in {**m["nodes"], **m["sources"]}.items():
        if n["resource_type"] not in ("model", "source"):
            continue
        name = f"{n['source_name']}.{n['name']}" if n["resource_type"] == "source" else n["name"]
        layer = "source" if n["resource_type"] == "source" else n["fqn"][1] if len(n["fqn"]) > 2 else "model"
        nodes.append({"id": uid, "name": name, "layer": layer, "description": n.get("description", "")})
        for dep in n.get("depends_on", {}).get("nodes", []):
            if dep.startswith(("model.", "source.")):
                edges.append([dep, uid])
    tests = sum(1 for n in m["nodes"].values() if n["resource_type"] == "test")
    return {"nodes": sorted(nodes, key=lambda x: x["id"]), "edges": sorted(edges), "tests": tests}


def main():
    con = duckdb.connect(str(DB), read_only=True)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "headline": rows(con, "select * from marts.fct_headline"),
        "monthly": rows(con, "select * exclude (month) from marts.fct_macro_monthly order by month"),
        "real_wages": rows(con, "select * exclude (quarter) from marts.fct_real_wages_quarterly order by quarter"),
        "loads": rows(con, """
            select source_id, mode, rows, status, problems, fetched_at
            from raw.load_log
            qualify row_number() over (partition by source_id order by fetched_at desc) = 1
            order by source_id"""),
        "lineage": lineage(),
    }
    report = ROOT / "out" / "contracts.json"
    if report.exists():
        data["contracts"] = json.loads(report.read_text())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))
    print(f"wrote {OUT} ({len(data['monthly'])} months, {len(data['real_wages'])} quarters, "
          f"{len(data['lineage']['nodes'])} models/sources, {data['lineage']['tests']} tests)")


if __name__ == "__main__":
    main()
