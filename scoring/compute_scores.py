"""Fast batch refresh for PAIMANA's scored portfolio.

Uses the same vectorized scoring path as PDF ingestion so batch refreshes and
event-triggered ingestion cannot drift apart.
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from extract_flash_report import score_extracted_projects

DATA_PATH = ROOT / "data" / "paimana_projects.csv"
OUT_PATH = ROOT / "scoring" / "scored_projects.json"

df = pd.read_csv(DATA_PATH)
ongoing = df[df["is_completed"] == 0].copy()
records = []
quality_cols = [
    "project_name", "ministry", "sector", "region", "sanction_date",
    "sanctioned_cost_cr", "planned_completion_date", "physical_progress_pct",
    "financial_progress_pct", "cumulative_expenditure_cr", "revised_cost_cr",
    "project_stage", "land_acquisition_status", "approval_delay_months",
    "contractor_track_record_score", "ministry_reporting_compliance_rate",
]
for row in ongoing.to_dict("records"):
    row["evidence_completeness_score"] = float(pd.Series(row).reindex(quality_cols).notna().mean())
    row["data_provenance"] = "PAIMANA project dataset"
    row.pop("is_completed", None)
    row.pop("planned_completion_date", None)
    row.pop("as_of_date", None)
    row.pop("actual_completion_date", None)
    row.pop("final_cost_overrun_pct", None)
    row.pop("final_delay_months", None)
    # pandas timestamps are not needed by the scoring engine and are intentionally removed.
    records.append(row)

blob = score_extracted_projects(records, "September 2026")
blob["generated_at"] = "2026-09-13"
# Preserve a truthful source note for the seeded portfolio.
blob["subset_note"] = f"{len(blob['projects'])} ongoing projects loaded from the PAIMANA project dataset; scores refreshed with the shared vectorized engine."

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(blob, f, indent=2)
with open(ROOT / "models" / "normalization_stats.json", "w", encoding="utf-8") as f:
    json.dump(blob.get("normalization", {}), f, indent=2)
print(f"Scored {len(blob['projects'])} ongoing projects -> {OUT_PATH}")
print(json.dumps(blob["portfolio_summary"], indent=2))
vals = np.array([p["confidence_score"] for p in blob["projects"]])
print({"confidence_unique": int(len(np.unique(vals))), "min": float(vals.min()), "median": float(np.median(vals)), "mean": float(vals.mean()), "max": float(vals.max())})
