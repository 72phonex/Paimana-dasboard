"""
Creates the indexed `projects` table and loads scoring/scored_projects.json
into it. Run this after scoring/compute_scores.py produces a fresh batch.

Postgres swap-in: this schema uses only ANSI-standard types (TEXT, REAL,
INTEGER) plus SQLite's AUTOINCREMENT-free INTEGER PRIMARY KEY. Porting to
Postgres means: swap sqlite3.connect() for psycopg2.connect()/SQLAlchemy,
and CREATE INDEX statements are already valid Postgres syntax as-is.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT / "backend" / "paimana.db")
SCORED_JSON = str(ROOT / "scoring" / "scored_projects.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    project_name TEXT,
    ministry TEXT,
    sector TEXT,
    region TEXT,
    sanction_date TEXT,
    sanctioned_cost_cr REAL,
    physical_progress_pct REAL,
    financial_progress_pct REAL,
    project_stage TEXT,
    risk_stage_block TEXT,
    land_acquisition_status TEXT,
    months_since_last_report INTEGER,
    consecutive_missed_cycles INTEGER,
    cost_revisions_count INTEGER DEFAULT 0,
    contractor_track_record_score REAL DEFAULT 0.5,
    financing_irregularity_flag INTEGER DEFAULT 0,
    approval_delay_months REAL DEFAULT 0,
    pred_cost_overrun_pct REAL,
    pred_delay_probability REAL,
    pred_delay_months REAL,
    risk_score REAL,
    confidence_score REAL,
    institutional_action TEXT,
    top_factors_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_risk_score ON projects(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_ministry ON projects(ministry);
CREATE INDEX IF NOT EXISTS idx_action ON projects(institutional_action);
CREATE INDEX IF NOT EXISTS idx_stage ON projects(project_stage);
"""


def main():
    with open(SCORED_JSON) as f:
        blob = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM projects")

    rows = []
    for p in blob["projects"]:
        rows.append((
            p["project_id"], p["project_name"], p["ministry"], p["sector"], p["region"],
            p["sanction_date"], p["sanctioned_cost_cr"], p["physical_progress_pct"],
            p["financial_progress_pct"], p["project_stage"], p["risk_stage_block"],
            p["land_acquisition_status"], p["months_since_last_report"], p["consecutive_missed_cycles"],
            0, 0.5, 0, 0,  # cost_revisions_count/contractor/financing/approval_delay -- backfilled below
            p["pred_cost_overrun_pct"], p["pred_delay_probability"], p["pred_delay_months"],
            p["risk_score"], p["confidence_score"], p["institutional_action"],
            json.dumps(p["top_factors"]),
        ))
    conn.executemany(
        """INSERT INTO projects (
            project_id, project_name, ministry, sector, region, sanction_date,
            sanctioned_cost_cr, physical_progress_pct, financial_progress_pct,
            project_stage, risk_stage_block, land_acquisition_status,
            months_since_last_report, consecutive_missed_cycles,
            cost_revisions_count, contractor_track_record_score,
            financing_irregularity_flag, approval_delay_months,
            pred_cost_overrun_pct, pred_delay_probability, pred_delay_months,
            risk_score, confidence_score, institutional_action, top_factors_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()

    # Backfill the fields not carried in scored_projects.json (it's a display
    # summary; the full feature row lives in the source CSV) so /recompute
    # has realistic starting values to update from.
    import pandas as pd
    src = pd.read_csv(str(ROOT / "data" / "paimana_projects.csv"))
    src = src.set_index("project_id")
    cur = conn.cursor()
    for pid in src.index:
        if pid not in {r[0] for r in rows}:
            continue
    for p in blob["projects"]:
        pid = p["project_id"]
        if pid in src.index:
            s = src.loc[pid]
            cur.execute(
                "UPDATE projects SET cost_revisions_count=?, contractor_track_record_score=?, "
                "financing_irregularity_flag=?, approval_delay_months=? WHERE project_id=?",
                (int(s["cost_revisions_count"]), float(s["contractor_track_record_score"]),
                 int(s["financing_irregularity_flag"]), float(s["approval_delay_months"]), pid),
            )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"Loaded {n} projects into {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
