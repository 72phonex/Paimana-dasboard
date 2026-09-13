"""
Shared scoring logic -- imported by BOTH scoring/compute_scores.py (the
nightly/full batch job) and backend/app.py (the event-triggered single-project
recompute). This is the concrete implementation of the whiteboard's central
claim: moving from time-triggered to event-triggered recompute is the SAME
scoring logic on a smaller trigger, not a second pipeline that could drift
out of sync with the batch one.

Normalization note: risk-score components that need population context
(cost-overrun severity, delay severity, approval-delay severity) are scaled
against FIXED bounds refreshed by the batch job (models/normalization_stats.json)
rather than a live min/max over "whatever's in the table right now". This is
what makes a single-project event-triggered score comparable to the rest of
the ranked list without re-scanning the whole portfolio -- exactly the
production pattern (bounds refreshed periodically in batch, applied inline
between refreshes).
"""
import json
import numpy as np
import pandas as pd

CAT_COLS = ["ministry", "sector", "region", "project_stage", "land_acquisition_status"]
NUM_COLS = [
    "sanctioned_cost_cr", "planned_duration_years", "months_since_sanction",
    "physical_progress_pct", "financial_progress_pct", "cost_revisions_count",
    "approval_delay_months", "financing_irregularity_flag",
    "contractor_track_record_score", "ministry_reporting_compliance_rate",
    "months_since_last_report", "consecutive_missed_cycles",
]
FEATURE_COLS = CAT_COLS + NUM_COLS

FRIENDLY_NAMES = {
    "sanctioned_cost_cr": "Sanctioned project cost",
    "planned_duration_years": "Planned execution duration",
    "months_since_sanction": "Time elapsed since sanction",
    "physical_progress_pct": "Physical progress",
    "financial_progress_pct": "Financial progress (expenditure ratio)",
    "cost_revisions_count": "Number of cost revisions",
    "approval_delay_months": "Approval delay",
    "financing_irregularity_flag": "Financing irregularity",
    "contractor_track_record_score": "Contractor track record",
    "ministry_reporting_compliance_rate": "Ministry reporting compliance",
    "months_since_last_report": "Months since last report",
    "consecutive_missed_cycles": "Consecutive missed reporting cycles",
    "ministry": "Ministry", "sector": "Sector", "region": "Region",
    "project_stage": "Project stage", "land_acquisition_status": "Land acquisition status",
}


def clip01(x, lo, hi):
    if hi <= lo:
        return 0.0
    return float(max(0.0, min(1.0, (x - lo) / (hi - lo))))


def encode_row(row: dict, enc) -> pd.DataFrame:
    """Turn a raw feature dict into the single-row encoded DataFrame the
    models expect, using the SAME fitted OrdinalEncoder as training."""
    raw = {c: str(row.get(c, "")) for c in CAT_COLS}
    raw_df = pd.DataFrame([raw])
    enc_vals = enc.transform(raw_df[CAT_COLS])[0]
    out = {c: enc_vals[i] for i, c in enumerate(CAT_COLS)}
    for c in NUM_COLS:
        out[c] = row.get(c, 0)
    return pd.DataFrame([out])[FEATURE_COLS]


def predict_row(row: dict, cost_model, delay_clf, delay_reg, enc) -> dict:
    x = encode_row(row, enc)
    return {
        "pred_cost_overrun_pct": float(cost_model.predict(x)[0]),
        "pred_delay_probability": float(delay_clf.predict_proba(x)[0, 1]),
        "pred_delay_months": float(max(0.0, delay_reg.predict(x)[0])),
    }


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def compute_evidence_confidence(row: dict, preds: dict | None = None) -> tuple[float, dict]:
    """Compute an interpretable project-specific evidence confidence score.

    The old implementation mostly rewarded recent reporting, which compressed
    most projects into the 90s. This version combines four independent signals:
    data completeness, freshness, model certainty, and internal consistency.
    """
    months_stale = max(0.0, min(_safe_float(row.get("months_since_last_report", 0)), 12.0))
    freshness = float(np.exp(-months_stale / 3.5))

    completeness = _safe_float(row.get("evidence_completeness_score", 0.75))
    completeness = float(np.clip(completeness, 0.0, 1.0))

    p_delay = _safe_float((preds or {}).get("pred_delay_probability", row.get("pred_delay_probability", 0.5)), 0.5)
    # 0.5 is the least certain point; 0/1 are the most certain points.
    model_certainty = float(np.clip(abs(2.0 * p_delay - 1.0), 0.0, 1.0))

    physical = _safe_float(row.get("physical_progress_pct", 0.0))
    financial = _safe_float(row.get("financial_progress_pct", 0.0))
    gap = min(abs(financial - physical) / 100.0, 1.0)
    cost_orig = max(_safe_float(row.get("sanctioned_cost_cr", 0.0)), 0.0)
    cost_rev = max(_safe_float(row.get("revised_cost_cr", cost_orig)), 0.0)
    expenditure = max(_safe_float(row.get("cumulative_expenditure_cr", 0.0)), 0.0)
    base = max(cost_rev or cost_orig, 1.0)
    spend_ratio = np.clip(expenditure / base, 0.0, 1.5)
    spend_progress_gap = min(abs((spend_ratio * 100.0) - financial) / 100.0, 1.0)
    consistency = float(np.clip(1.0 - (0.65 * gap + 0.35 * spend_progress_gap), 0.0, 1.0))

    cost_signal = float(1.0 - np.exp(-max(0.0, _safe_float((preds or {}).get("pred_cost_overrun_pct", 0.0))) / 30.0))
    delay_signal = float(1.0 - np.exp(-max(0.0, _safe_float((preds or {}).get("pred_delay_months", 0.0))) / 36.0))
    prediction_concordance = float(np.clip(1.0 - np.std([p_delay, cost_signal, delay_signal]) * 1.8, 0.0, 1.0))

    raw_quality = (
        0.35 * completeness +
        0.15 * freshness +
        0.20 * model_certainty +
        0.15 * consistency +
        0.15 * prediction_concordance
    )
    # Non-linear compression prevents a portfolio with broadly complete
    # monthly reporting from collapsing into an indistinguishable wall of 95-99%.
    # A project must be consistently strong across all evidence dimensions
    # to reach the highest band.
    score = 100.0 * (raw_quality ** 3)
    score = round(float(np.clip(score, 8.0, 98.0)), 1)
    breakdown = {
        "data_completeness": round(completeness * 100.0, 1),
        "data_freshness": round(freshness * 100.0, 1),
        "model_certainty": round(model_certainty * 100.0, 1),
        "internal_consistency": round(consistency * 100.0, 1),
        "prediction_concordance": round(prediction_concordance * 100.0, 1),
        "formula": "35% completeness + 15% freshness + 20% model certainty + 15% internal consistency + 15% prediction concordance",
    }
    return score, breakdown


def compute_risk_and_confidence(row: dict, preds: dict, norm: dict) -> dict:
    """Compute risk and project-specific evidence confidence."""
    cost_component = clip01(max(0.0, preds["pred_cost_overrun_pct"]), 0, norm["cost_overrun_p99"])
    delay_severity = preds["pred_delay_probability"] * max(0.0, preds["pred_delay_months"])
    delay_component = clip01(delay_severity, 0, norm["delay_severity_p99"])

    land_penalty = {"not_started": 1.0, "partial": 0.5, "complete": 0.0}.get(
        row.get("land_acquisition_status"), 0.3
    )
    approval_component = clip01(row.get("approval_delay_months", 0), 0, norm["approval_delay_p99"])
    contractor_component = 1 - float(row.get("contractor_track_record_score", 0.5))
    financing_component = float(row.get("financing_irregularity_flag", 0))

    structural_component = (
        0.35 * land_penalty + 0.25 * approval_component +
        0.25 * contractor_component + 0.15 * financing_component
    )

    risk_score = 100 * (0.40 * cost_component + 0.35 * delay_component + 0.25 * structural_component)

    consecutive_missed = int(row.get("consecutive_missed_cycles", 0))
    if consecutive_missed >= 3:
        risk_score += 8.0
    risk_score = round(float(np.clip(risk_score, 0, 100)), 1)

    confidence_score, confidence_breakdown = compute_evidence_confidence(row, preds)

    stuck_structural = (
        row.get("land_acquisition_status") == "not_started" and consecutive_missed >= 3
    )
    if stuck_structural and risk_score >= 18:
        action = "PRAGATI candidate"
    elif float(row.get("sanctioned_cost_cr", 0)) >= 500 and risk_score >= 45:
        action = "Escalate to PMG"
    elif risk_score >= 30:
        action = "Flag to line ministry"
    else:
        action = "Routine monitoring"

    risk_stage_block = (
        "Pre-construction risk (approvals/land/clearances)"
        if row.get("project_stage") == "pre_construction"
        else "Construction-stage risk (execution/contractor)"
    )

    return {
        "risk_score": risk_score,
        "confidence_score": confidence_score,
        "confidence_breakdown": confidence_breakdown,
        "institutional_action": action,
        "risk_stage_block": risk_stage_block,
    }


def top_factors(row: dict, base_pred: float, cost_model, enc, baseline_fill: dict, n=3):
    """Single-feature ablation local attribution against the cost-overrun
    model -- see scoring/compute_scores.py module docstring for why this
    substitutes for shap.TreeExplainer in this sandbox."""
    x_row = encode_row(row, enc).iloc[0]
    contributions = []
    for c in FEATURE_COLS:
        ablated = x_row.copy()
        ablated[c] = baseline_fill[c]
        ablated_pred = float(cost_model.predict(pd.DataFrame([ablated])[FEATURE_COLS])[0])
        delta = base_pred - ablated_pred
        contributions.append((c, delta))
    contributions.sort(key=lambda t: abs(t[1]), reverse=True)
    return [
        {
            "factor": FRIENDLY_NAMES.get(c, c),
            "direction": "increases risk" if delta > 0 else "decreases risk",
            "impact_pp": round(float(delta), 2),
        }
        for c, delta in contributions[:n]
    ]
