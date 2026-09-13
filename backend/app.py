"""
FastAPI backend for the PAIMANA early-warning dashboard & Admin Console.
Team Quantumsyntax — SIH 2026 (MoSPI/IPMD Central Sector Projects).

Features:
- Dual-mode support: Executive Ledger & Admin Console
- Multi-PDF batch ingestion & Table 6 extraction
- Dynamic training vs prediction dataset assignment
- Instant machine learning model retraining & validation metrics updates
- Fast in-memory inference & zero-lag indexed lookups
"""
import datetime
import hashlib
import json
import sqlite3
import sys
import os
import re
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Optional, List
from pathlib import Path

# Fix Windows DLL loading for Python 3.8+ and 3.14 (scipy.libs, numpy.libs, pandas.libs)
user_site = Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages"
if user_site.exists():
    for libs_dir in user_site.glob("*.libs"):
        if libs_dir.is_dir():
            try:
                os.add_dll_directory(str(libs_dir))
            except Exception:
                pass

import joblib
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scoring"))
sys.path.insert(0, str(ROOT / "pipeline"))
import score_lib as sl
import extract_flash_report as efr
import retrain_service

MODEL_DIR = ROOT / "models"
SCORED_JSON = ROOT / "scoring" / "scored_projects.json"
DB_PATH = ROOT / "backend" / "paimana.db"
NORM_PATH = MODEL_DIR / "normalization_stats.json"
REPORTS_DIR = ROOT / "public" / "reports"
REGISTRY_PATH = REPORTS_DIR / "registry.json"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PAIMANA Early-Warning & Admin API", version="0.3.0")

# Background ingestion queue: the HTTP request only stages files and enqueues work.
# Heavy PDF parsing / ML scoring runs outside the request thread so large reports do not
# make the upload UI appear frozen. Two workers prevent CPU contention on student laptops.
INGEST_ROOT = ROOT / "runtime" / "ingestion"
INGEST_ROOT.mkdir(parents=True, exist_ok=True)
_ingest_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="paimana-ingest")
_ingest_lock = threading.Lock()
_ingest_jobs: dict[str, dict] = {}

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def load_models_and_metrics():
    global _cost_model, _delay_clf, _delay_reg, _enc, _norm, _metrics
    _cost_model = joblib.load(f"{MODEL_DIR}/cost_overrun_model.joblib")
    _delay_clf = joblib.load(f"{MODEL_DIR}/delay_probability_model.joblib")
    _delay_reg = joblib.load(f"{MODEL_DIR}/delay_duration_model.joblib")
    _enc = joblib.load(f"{MODEL_DIR}/categorical_encoder.joblib")
    with open(NORM_PATH) as f:
        _norm = json.load(f)
    with open(f"{MODEL_DIR}/training_metrics.json") as f:
        _metrics = json.load(f)


load_models_and_metrics()

if SCORED_JSON.exists():
    with open(SCORED_JSON) as f:
        _scored_blob = json.load(f)
else:
    _scored_blob = {"portfolio_summary": {}, "model_metrics": {}, "backtest_case": {}}



def _job_update(job_id: str, **updates):
    with _ingest_lock:
        job = _ingest_jobs.get(job_id)
        if job:
            job.update(updates)


def _process_ingestion_job(job_id: str, staged_files: list[dict], purpose: str):
    _job_update(job_id, status="processing", stage="parsing", progress=20, message="Document staged. Parsing project tables…")
    reg = get_registry()
    processed = []
    try:
        total = len(staged_files)
        for idx, item in enumerate(staged_files, start=1):
            path = Path(item["path"])
            ext = item["ext"]
            name = item["filename"]
            sha256 = item.get("sha256")
            existing = next((r for r in reg.get("reports", []) if sha256 and r.get("sha256") == sha256), None)
            if existing:
                processed.append(existing)
                _job_update(job_id, current_file=name, stage="complete", progress=100, message=f"Duplicate document detected; reused existing dataset for {name}.")
                try: path.unlink(missing_ok=True)
                except Exception: pass
                continue
            _job_update(
                job_id,
                current_file=name,
                stage="parsing",
                progress=max(20, min(70, 20 + int((idx - 1) / max(total, 1) * 35))),
                message=f"Extracting structured project data from {name}…",
            )

            if ext == ".csv":
                import pandas as pd
                df_check = pd.read_csv(path)
                req_cols = ["project_id", "project_name", "sanctioned_cost_cr"]
                missing = [c for c in req_cols if c not in df_check.columns]
                if missing:
                    raise ValueError(f"CSV validation failed for {name}: missing required columns {missing}")
                if "physical_progress_pct" in df_check.columns:
                    invalid_pct = df_check[(df_check.physical_progress_pct < 0) | (df_check.physical_progress_pct > 100)]
                    if not invalid_pct.empty:
                        raise ValueError(f"CSV validation failed for {name}: {len(invalid_pct)} invalid physical_progress_pct rows")

            _job_update(job_id, stage="scoring", progress=max(55, min(92, 55 + int(idx / max(total, 1) * 25))), message=f"Running ML risk, delay and confidence scoring for {name}…")
            scored = efr.extract_and_score_file(path)

            gen_month = scored.get("generated_at", Path(name).stem)
            safe_slug = re_safe_slug(gen_month)
            out_filename = f"scored_projects_{safe_slug}.json"
            out_path = REPORTS_DIR / out_filename
            tmp_out = out_path.with_suffix(out_path.suffix + ".tmp")
            with open(tmp_out, "w", encoding="utf-8") as f:
                json.dump(scored, f, indent=2)
            os.replace(tmp_out, out_path)

            projects = scored.get("projects", [])
            completed_count = sum(1 for proj in projects if proj.get("physical_progress_pct", 0) >= 90)
            report_id = f"custom_{safe_slug}_{uuid.uuid4().hex[:8]}"
            new_entry = {
                "id": report_id,
                "title": f"{gen_month} {'Flash Report' if ext == '.pdf' else 'Dataset'}",
                "filename": out_filename,
                "month": gen_month,
                "badge": "Adaptive PDF" if ext == ".pdf" else "CSV Dataset",
                "purpose": purpose if purpose in ["training", "prediction"] else "prediction",
                "project_count": len(projects),
                "completed_count": completed_count,
                "is_active": False,
                "uploaded_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ingestion_job_id": job_id,
                "sha256": sha256,
            }
            existing_idx = next((i for i, r in enumerate(reg["reports"]) if r.get("filename") == out_filename), -1)
            if existing_idx >= 0:
                reg["reports"][existing_idx] = new_entry
            else:
                reg["reports"].insert(0, new_entry)
            processed.append(new_entry)

            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

        save_registry(reg)
        _job_update(job_id, status="completed", stage="complete", progress=100, message=f"Processed {len(processed)} dataset(s).", reports=processed, uploaded_count=len(processed))
    except Exception as exc:
        _job_update(job_id, status="failed", stage="error", progress=100, message=str(exc), error=str(exc), reports=processed, uploaded_count=len(processed))
        for item in staged_files:
            try:
                Path(item["path"]).unlink(missing_ok=True)
            except Exception:
                pass


def re_safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value).strip().lower()).strip("_")
    return cleaned or f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"


def get_registry() -> dict:
    if not REGISTRY_PATH.exists():
        initial = {
            "reports": [
                {
                    "id": "june_2026",
                    "title": "June 2026 Flash Report",
                    "filename": "scored_projects_june_2026.json",
                    "month": "June 2026",
                    "badge": "Official",
                    "purpose": "prediction",
                    "project_count": 1847,
                    "completed_count": 48,
                    "is_active": True,
                    "uploaded_at": "2026-06-30 18:00:00"
                },
                {
                    "id": "may_2026",
                    "title": "May 2026 Flash Report",
                    "filename": "scored_projects_may_2026.json",
                    "month": "May 2026",
                    "badge": "Official",
                    "purpose": "prediction",
                    "project_count": 1987,
                    "completed_count": 52,
                    "is_active": False,
                    "uploaded_at": "2026-05-31 18:00:00"
                },
                {
                    "id": "april_2026",
                    "title": "April 2026 Flash Report",
                    "filename": "scored_projects_april_2026.json",
                    "month": "April 2026",
                    "badge": "Official",
                    "purpose": "training",
                    "project_count": 1981,
                    "completed_count": 61,
                    "is_active": False,
                    "uploaded_at": "2026-04-30 18:00:00"
                }
            ]
        }
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2)
        return initial

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry_data: dict):
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_project(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["top_factors"] = json.loads(d["top_factors_json"])
    del d["top_factors_json"]
    return d


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_metrics": _metrics.get("cost_overrun_mae_pp"),
        "last_trained_at": _metrics.get("last_trained_at", "Baseline"),
    }


# ---------------------------------------------------------------------------
# Public Report Endpoints (Used by Dashboard)
# ---------------------------------------------------------------------------

@app.get("/reports")
def list_reports():
    reg = get_registry()
    reports = reg.get("reports", [])
    
    # Check actual counts dynamically
    for r in reports:
        fp = REPORTS_DIR / r.get("filename", "")
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    r["project_count"] = len(d.get("projects", []))
            except Exception:
                pass
    return reports


@app.get("/reports/{report_id}")
def get_report_data(report_id: str):
    reg = get_registry()
    matching = next((r for r in reg.get("reports", []) if r.get("id") == report_id or r.get("filename") == report_id), None)
    if matching:
        fp = REPORTS_DIR / matching["filename"]
    else:
        fp = REPORTS_DIR / report_id

    if not fp.exists():
        # Fallback check in scoring directory
        fallback_scoring = ROOT / "scoring" / report_id
        if fallback_scoring.exists():
            fp = fallback_scoring
        else:
            raise HTTPException(404, f"Report '{report_id}' not found on disk")
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Admin Console Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/admin/reports")
def admin_list_reports():
    return list_reports()


@app.get("/api/admin/metrics")
def admin_get_metrics():
    with open(MODEL_DIR / "training_metrics.json", "r", encoding="utf-8") as f:
        metrics = json.load(f)
    return metrics


@app.post("/api/admin/upload-multiple")
async def admin_upload_multiple_pdfs(
    files: List[UploadFile] = File(...),
    purpose: str = Form("prediction")
):
    """Stage upload bytes quickly, then process in a background ingestion job."""
    if not files:
        raise HTTPException(400, "No files uploaded")

    job_id = f"ing_{uuid.uuid4().hex[:12]}"
    staged = []
    try:
        for file in files:
            ext = Path(file.filename or "").suffix.lower()
            if ext not in [".pdf", ".csv"]:
                continue
            safe_name = re_safe_slug(Path(file.filename).stem) + ext
            target = INGEST_ROOT / f"{job_id}_{safe_name}"
            digest = hashlib.sha256()
            with open(target, "wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    out.write(chunk)
            staged.append({"path": str(target), "filename": file.filename, "ext": ext, "sha256": digest.hexdigest()})

        if not staged:
            raise HTTPException(400, "No valid PDF or CSV files uploaded")

        with _ingest_lock:
            _ingest_jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "stage": "queued",
                "progress": 5,
                "message": "Files uploaded. Waiting for ingestion worker…",
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "files": [x["filename"] for x in staged],
                "file_hashes": [x.get("sha256") for x in staged],
                "reports": [],
                "uploaded_count": 0,
            }
        _ingest_executor.submit(_process_ingestion_job, job_id, staged, purpose)
        return {"status": "accepted", "job_id": job_id, "queued_count": len(staged), "files": [x["filename"] for x in staged]}
    except HTTPException:
        for item in staged:
            try: Path(item["path"]).unlink(missing_ok=True)
            except Exception: pass
        raise
    except Exception as exc:
        for item in staged:
            try: Path(item["path"]).unlink(missing_ok=True)
            except Exception: pass
        raise HTTPException(500, f"Upload staging failed: {exc}")


@app.get("/api/admin/ingestion/{job_id}")
def admin_get_ingestion_job(job_id: str):
    with _ingest_lock:
        job = _ingest_jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Ingestion job not found")
        return dict(job)


class UpdateReportRequest(BaseModel):
    purpose: Optional[str] = None
    is_active: Optional[bool] = None
    title: Optional[str] = None


@app.patch("/api/admin/reports/{report_id}")
def admin_update_report(report_id: str, req: UpdateReportRequest):
    reg = get_registry()
    matching = next((r for r in reg.get("reports", []) if r.get("id") == report_id), None)
    if not matching:
        raise HTTPException(404, f"Report '{report_id}' not found")

    if req.purpose is not None:
        if req.purpose not in ["training", "prediction"]:
            raise HTTPException(400, "purpose must be 'training' or 'prediction'")
        matching["purpose"] = req.purpose

    if req.title is not None:
        matching["title"] = req.title

    if req.is_active is not None:
        if req.is_active:
            for r in reg.get("reports", []):
                r["is_active"] = (r.get("id") == report_id)
        else:
            matching["is_active"] = False

    save_registry(reg)
    return {"status": "success", "report": matching}


@app.delete("/api/admin/reports/{report_id}")
def admin_delete_report(report_id: str):
    reg = get_registry()
    idx = next((i for i, r in enumerate(reg.get("reports", [])) if r.get("id") == report_id), -1)
    if idx == -1:
        raise HTTPException(404, f"Report '{report_id}' not found")

    deleted_report = reg["reports"].pop(idx)
    
    # If the deleted report was active, make the first available report active
    if deleted_report.get("is_active") and reg["reports"]:
        reg["reports"][0]["is_active"] = True

    # Try removing the json file from public/reports/
    fn = deleted_report.get("filename")
    if fn:
        fp = REPORTS_DIR / fn
        if fp.exists() and "demo" not in fn:
            try:
                fp.unlink()
            except Exception as e:
                print(f"Warning deleting file {fp}: {e}")

    save_registry(reg)
    return {"status": "success", "deleted_id": report_id, "reports": reg["reports"]}


@app.post("/api/admin/train")
def admin_train_models():
    """
    Retrain all machine learning models using baseline data plus
    any reports currently tagged as purpose='training'.
    """
    try:
        metrics = retrain_service.retrain_paimana_models()
        load_models_and_metrics()
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        raise HTTPException(500, f"Retraining failed: {str(e)}")


@app.post("/api/admin/predict/{report_id}")
def admin_predict_report(report_id: str):
    """
    Re-scores an existing dataset using the latest retrained models.
    """
    reg = get_registry()
    matching = next((r for r in reg.get("reports", []) if r.get("id") == report_id), None)
    if not matching:
        raise HTTPException(404, f"Report '{report_id}' not found")

    fp = REPORTS_DIR / matching["filename"]
    if not fp.exists():
        raise HTTPException(404, f"File {matching['filename']} does not exist")

    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)

    projects = data.get("projects", [])
    if not projects:
        raise HTTPException(400, "No projects in this dataset to score")

    # Score using vectorized scoring
    rescored = efr.score_extracted_projects(projects, matching.get("month", "Updated Report"))
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(rescored, f, indent=2)

    return {
        "status": "success",
        "report_id": report_id,
        "rescored_projects_count": len(rescored["projects"]),
        "portfolio_summary": rescored.get("portfolio_summary"),
    }


# ---------------------------------------------------------------------------
# Legacy Portfolio & Project Query Endpoints
# ---------------------------------------------------------------------------

@app.get("/portfolio/summary")
def portfolio_summary():
    return _scored_blob["portfolio_summary"] | {
        "model_metrics": _scored_blob["model_metrics"],
        "backtest_case": _scored_blob["backtest_case"],
    }


@app.get("/projects")
def list_projects(
    ministry: Optional[str] = None,
    sector: Optional[str] = None,
    institutional_action: Optional[str] = None,
    project_stage: Optional[str] = None,
    min_risk: float = 0.0,
    sort: str = "risk_score",
    limit: int = 50,
    offset: int = 0,
):
    allowed_sort = {"risk_score", "confidence_score", "sanctioned_cost_cr"}
    if sort not in allowed_sort:
        raise HTTPException(400, f"sort must be one of {allowed_sort}")

    clauses, params = ["risk_score >= ?"], [min_risk]
    if ministry:
        clauses.append("ministry = ?"); params.append(ministry)
    if sector:
        clauses.append("sector = ?"); params.append(sector)
    if institutional_action:
        clauses.append("institutional_action = ?"); params.append(institutional_action)
    if project_stage:
        clauses.append("project_stage = ?"); params.append(project_stage)
    where = " AND ".join(clauses)

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM projects WHERE {where} ORDER BY {sort} DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        total = conn.execute(f"SELECT COUNT(*) c FROM projects WHERE {where}", params).fetchone()["c"]

    return {"total": total, "limit": limit, "offset": offset, "projects": [row_to_project(r) for r in rows]}


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "project not found")
    return row_to_project(row)


class RecomputeRequest(BaseModel):
    physical_progress_pct: Optional[float] = None
    financial_progress_pct: Optional[float] = None
    land_acquisition_status: Optional[str] = None
    approval_delay_months: Optional[float] = None
    financing_irregularity_flag: Optional[int] = None
    cost_revisions_count: Optional[int] = None
    months_since_last_report: Optional[int] = None
    consecutive_missed_cycles: Optional[int] = None
    contractor_track_record_score: Optional[float] = None


@app.post("/projects/{project_id}/simulate")
def simulate_project(project_id: str, patch: RecomputeRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "project not found")
        p = dict(row)

    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    p.update(updates)

    pred_cost_overrun_pct = sl.predict_cost_overrun(_cost_model, _enc, p)
    pred_delay_probability = sl.predict_delay_probability(_delay_clf, _enc, p)
    pred_delay_months = sl.predict_delay_duration(_delay_reg, _enc, p)

    cost_score = sl.normalize_cost_overrun(pred_cost_overrun_pct, _norm)
    delay_score = sl.normalize_delay_duration(pred_delay_months, _norm)
    p["risk_score"] = sl.compute_risk_score(cost_score, delay_score, pred_delay_probability, p)
    p["confidence_score"] = sl.compute_confidence_score(p)
    p["institutional_action"] = sl.assign_institutional_action(
        p["risk_score"], p["confidence_score"], p.get("sanctioned_cost_cr", 0)
    )
    p["pred_cost_overrun_pct"] = pred_cost_overrun_pct
    p["pred_delay_probability"] = pred_delay_probability
    p["pred_delay_months"] = pred_delay_months

    # Also compute simulated attribution
    p["attribution_factors"] = sl.top_factors(_cost_model, _delay_clf, _delay_reg, _enc, p, _norm)

    return row_to_project(p)


@app.post("/projects/{project_id}/recompute")
def recompute_project(project_id: str, patch: RecomputeRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "project not found")
        p = dict(row)

    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    p.update(updates)

    pred_cost_overrun_pct = sl.predict_cost_overrun(_cost_model, _enc, p)
    pred_delay_probability = sl.predict_delay_probability(_delay_clf, _enc, p)
    pred_delay_months = sl.predict_delay_duration(_delay_reg, _enc, p)

    cost_score = sl.normalize_cost_overrun(pred_cost_overrun_pct, _norm)
    delay_score = sl.normalize_delay_duration(pred_delay_months, _norm)
    p["risk_score"] = sl.compute_risk_score(cost_score, delay_score, pred_delay_probability, p)

    p["confidence_score"] = sl.compute_confidence_score(p)
    p["institutional_action"] = sl.assign_institutional_action(
        p["risk_score"], p["confidence_score"], p.get("sanctioned_cost_cr", 0)
    )
    p["pred_cost_overrun_pct"] = pred_cost_overrun_pct
    p["pred_delay_probability"] = pred_delay_probability
    p["pred_delay_months"] = pred_delay_months

    top_factors = sl.top_factors(_cost_model, _delay_clf, _delay_reg, _enc, p, _norm)

    with get_db() as conn:
        conn.execute(
            """
            UPDATE projects SET
                risk_score = ?, confidence_score = ?, institutional_action = ?,
                pred_cost_overrun_pct = ?, pred_delay_probability = ?,
                pred_delay_months = ?, physical_progress_pct = ?,
                financial_progress_pct = ?, land_acquisition_status = ?,
                approval_delay_months = ?, financing_irregularity_flag = ?,
                cost_revisions_count = ?, months_since_last_report = ?,
                consecutive_missed_cycles = ?, contractor_track_record_score = ?,
                top_factors_json = ?
            WHERE project_id = ?
            """,
            (
                p["risk_score"], p["confidence_score"], p["institutional_action"],
                p["pred_cost_overrun_pct"], p["pred_delay_probability"],
                p["pred_delay_months"], p["physical_progress_pct"],
                p["financial_progress_pct"], p["land_acquisition_status"],
                p["approval_delay_months"], p["financing_irregularity_flag"],
                p["cost_revisions_count"], p["months_since_last_report"],
                p["consecutive_missed_cycles"], p["contractor_track_record_score"],
                json.dumps(top_factors), project_id,
            ),
        )
        conn.commit()

    p["top_factors"] = top_factors
    return p


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
