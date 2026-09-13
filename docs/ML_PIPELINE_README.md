# PAIMANA Predictive Analytics & Early-Warning System
Team Quantumsyntax — SIH 2026, problem statement SIH26103 (MoSPI/IPMD)

Full working pipeline: synthetic data → ML models → scoring → API → dashboard.
Built to match the whiteboard architecture and differentiation strategy in
`PAIMANA_System_Design.docx` / the original solution brief.

## What's real vs. substituted (read this first)

Everything below actually runs and produces real numbers from real (synthetic)
data — nothing is mocked or hand-waved. Two substitutions were made only
because this build environment has no network access to `pip install`
anything not already present; both are documented, isolated, and trivial to
swap for the real thing in an environment with internet access:

| Brief calls for | Built with | Why | Swap effort |
|---|---|---|---|
| XGBoost / LightGBM | `sklearn.HistGradientBoosting{Regressor,Classifier}` | Same gradient-boosted-tree family, same `.fit`/`.predict` API, preinstalled | ~5 lines in `pipeline/train_models.py` |
| SHAP | Single-feature ablation attribution (`scoring/score_lib.py::top_factors`) | A documented approximation of a Shapley decomposition (it's the one-feature-at-a-time special case), needs zero extra dependencies | ~10 lines, swap for `shap.TreeExplainer(model)` |
| FastAPI running live | FastAPI source code, syntax-verified, logic-tested directly (see below) | No network to `pip install fastapi` in this sandbox | `pip install -r backend/requirements.txt && uvicorn backend.app:app --reload` on any machine with internet |
| PostgreSQL | SQLite (`backend/paimana.db`) | Zero-setup, stdlib-only, same indexed-read pattern | Swap `sqlite3.connect()` for `psycopg2`/SQLAlchemy; schema is already ANSI SQL |

The `/recompute` event-triggered scoring path (the riskiest piece from the
whiteboard) was verified by calling the exact same functions the API endpoint
calls, directly in Python — see the "Event-triggered recompute, verified"
section below for real output.

## Directory structure

```
data/       generate_synthetic_data.py   -> paimana_projects.csv
pipeline/   train_models.py              -> models/*.joblib, training_metrics.json
scoring/    score_lib.py                 shared scoring logic (batch + API both call this)
            compute_scores.py            batch job -> scored_projects.json, normalization_stats.json
backend/    app.py                       FastAPI app (list/detail/recompute endpoints)
            init_db.py                   loads scored_projects.json into indexed SQLite
            requirements.txt
dashboard/  (delivered separately as an interactive artifact)
```

## Run order (fresh machine, with internet)

```bash
pip install pandas numpy scikit-learn joblib
python data/generate_synthetic_data.py      # ~5s,  writes paimana_projects.csv
python pipeline/train_models.py             # ~10s, writes models/*.joblib + metrics
python scoring/compute_scores.py            # ~2min, writes scored_projects.json
                                             #        (ablation attribution is the slow part)
pip install -r backend/requirements.txt
python backend/init_db.py                   # loads scored_projects.json -> SQLite
uvicorn backend.app:app --reload --port 8000
```

Then: `curl localhost:8000/portfolio/summary` or open `localhost:8000/docs`
for the interactive API explorer FastAPI generates automatically.

## Calibration (why the numbers are defensible)

Every distribution parameter in `generate_synthetic_data.py` traces to a
cited public MoSPI Flash Report figure (overrun %, delay-severity buckets,
ministry project-count shares, current portfolio size) — see the module
docstring for the full source list. This is what "validate the way an
auditor would" (differentiation move #4) requires: an evaluator should be
able to check any distributional claim against a public number.

## Validation discipline

`pipeline/train_models.py` uses a **time-based split** — train on projects
sanctioned before 2019, test on projects sanctioned 2019+ — not a random
split, because a random split lets the model see later-sanctioned projects
during training and evaluate on earlier ones, which leaks information a
real early-warning system would never have. Out-of-time results:

- Cost-overrun MAE: ~5.3 percentage points
- Delay-probability AUC: ~0.98
- Delay-duration MAE: ~0.4 months

A concrete backtested case is saved in `models/training_metrics.json` and
surfaced in `scored_projects.json["backtest_case"]` — a specific project the
model would have flagged as high-risk using only pre-completion features,
months before the actual overrun became final. This proves the early-warning
claim (differentiation move #4) rather than asserting it.

## Event-triggered recompute, verified

Ran directly against `score_lib.py` (the same functions `POST
/projects/{id}/recompute` calls): a low-risk, high-confidence project that
goes silent for 4 reporting cycles and has its land-acquisition status
regress to "not started" —

| | Before | After |
|---|---|---|
| risk_score | 0.4 | 24.6 |
| confidence_score | 85.5 | 48.8 |
| institutional_action | Routine monitoring | **PRAGATI candidate** |

This is the whiteboard's central design decision made concrete: the project
moved up the ranked list *because* it went quiet, not just got a wider error
bar. Confidence and risk are reported separately and never blended into one
number, on purpose.

## Institutional-action labels (differentiation move #1)

`score_lib.compute_risk_and_confidence` outputs MoSPI's actual escalation
language instead of generic High/Medium/Low:
- **PRAGATI candidate** — structurally stuck (land not started + 3+ missed
  reporting cycles) and materially risky.
- **Escalate to PMG** — ≥ Rs 500 cr (PMG's actual threshold) and risk_score ≥ 45.
- **Flag to line ministry** — risk_score ≥ 30.
- **Routine monitoring** — below threshold.

## Two-stage modeling (differentiation move #2)

Every project carries `project_stage` (pre_construction / construction) and
a corresponding `risk_stage_block` label, so a project stuck in land
acquisition is never conflated with one stuck on a slow contractor —
distinct feature blocks, distinct dashboard framing, per MoSPI's 2024
milestone-based methodology.

## Confidence scoring (the riskiest piece — Approach A, as scoped on the whiteboard)

`score_lib.compute_risk_and_confidence` implements the rule-based
completeness score chosen for the demo: reporting staleness, consecutive
missed cycles, and ministry-level historical compliance, combined
transparently (weights are visible in the source, not learned/hidden).
Approach B (learned/conformal confidence) is the documented production
roadmap item, not built here — see the design doc for the full comparison.
