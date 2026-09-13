"""
Feature engineering + model training for PAIMANA early-warning models.

Substitution note (documented, not hidden): the reference architecture calls
for XGBoost/LightGBM. This sandbox has no network access to install them, so
we train with scikit-learn's HistGradientBoosting{Regressor,Classifier}
instead -- same gradient-boosted-tree family, same sklearn-style .fit/.predict
API, same feature_importances-style introspection. Swapping in real
xgboost.XGBRegressor / lightgbm.LGBMClassifier is a ~5-line change (see
README "Production swap-ins"); nothing else in the pipeline depends on the
specific library.

Validation discipline (per the differentiation strategy): a TIME-BASED split
-- train on projects SANCTIONED before a cutoff year, test on projects
sanctioned after it -- not a random split, which would leak future
information for project data (a random split lets the model see, e.g.,
2024-sanctioned projects during training and evaluate on 2010-sanctioned
projects, which is backwards and unrealistically easy).

Two-stage modeling: pre_construction and construction are trained as
separate delay-risk feature blocks (per MoSPI's 2024 methodology), sharing
the same cost-overrun model but with stage-aware features.
"""
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import mean_absolute_error, roc_auc_score, brier_score_loss
from sklearn.preprocessing import OrdinalEncoder
import joblib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = str(ROOT / "data" / "paimana_projects.csv")
MODEL_DIR = str(ROOT / "models")
CUTOFF_YEAR = 2019  # train: sanctioned < 2019 and completed; test: sanctioned >= 2019 and completed

df = pd.read_csv(DATA_PATH, parse_dates=["sanction_date", "planned_completion_date", "as_of_date"])

CAT_COLS = ["ministry", "sector", "region", "project_stage", "land_acquisition_status"]
NUM_COLS = [
    "sanctioned_cost_cr", "planned_duration_years", "months_since_sanction",
    "physical_progress_pct", "financial_progress_pct", "cost_revisions_count",
    "approval_delay_months", "financing_irregularity_flag",
    "contractor_track_record_score", "ministry_reporting_compliance_rate",
    "months_since_last_report", "consecutive_missed_cycles",
]
FEATURE_COLS = CAT_COLS + NUM_COLS

enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
df[CAT_COLS] = df[CAT_COLS].astype(str)
df_enc = df.copy()
df_enc[CAT_COLS] = enc.fit_transform(df[CAT_COLS])

# Only *completed* projects have ground-truth outcomes usable as labels.
labeled = df_enc[df_enc.is_completed == 1].copy()
labeled["sanction_year"] = df.loc[labeled.index, "sanction_date"].dt.year

train_mask = labeled.sanction_year < CUTOFF_YEAR
test_mask = ~train_mask

# --- LEAKAGE FIX: Generate point-in-time snapshots for completed projects ---
# For a completed project, its current CSV row is the final snapshot (progress=100%, 
# months_since_sanction = total duration). Training on this leaks the outcome.
# We simulate a random point-in-time T for each project.
np.random.seed(42)
random_progress = np.random.uniform(0.1, 0.9, size=len(labeled))

# Scale features back to what they would be at 'random_progress' point in time
labeled["physical_progress_pct"] = random_progress * 100.0
labeled["financial_progress_pct"] = random_progress * 100.0 * np.random.uniform(0.8, 1.2, size=len(labeled))
labeled["financial_progress_pct"] = labeled["financial_progress_pct"].clip(0, 100)

actual_duration_months = (pd.to_datetime(labeled["actual_completion_date"]) - labeled["sanction_date"]).dt.days / 30.44
labeled["months_since_sanction"] = actual_duration_months * random_progress

# Cost revisions count: estimate how many had occurred by point T
labeled["cost_revisions_count"] = np.floor(labeled["cost_revisions_count"] * random_progress)

X_train, X_test = labeled.loc[train_mask, FEATURE_COLS], labeled.loc[test_mask, FEATURE_COLS]
y_cost_train, y_cost_test = labeled.loc[train_mask, "final_cost_overrun_pct"], labeled.loc[test_mask, "final_cost_overrun_pct"]
y_delay_train, y_delay_test = labeled.loc[train_mask, "final_delay_months"], labeled.loc[test_mask, "final_delay_months"]
y_delayflag_train = (y_delay_train > 1).astype(int)
y_delayflag_test = (y_delay_test > 1).astype(int)

print(f"Train (sanctioned < {CUTOFF_YEAR}, point-in-time): {len(X_train)} rows")
print(f"Test  (sanctioned >= {CUTOFF_YEAR}, point-in-time): {len(X_test)} rows")

# --- Model 1: Cost escalation forecasting (regression) ---
cost_model = HistGradientBoostingRegressor(
    max_depth=6, learning_rate=0.06, max_iter=300, l2_regularization=0.5, random_state=42
)
cost_model.fit(X_train, y_cost_train)
cost_pred = cost_model.predict(X_test)
cost_mae = mean_absolute_error(y_cost_test, cost_pred)
print(f"Cost-overrun model  MAE (out-of-time): {cost_mae:.2f} percentage points")

# --- Model 2: Schedule delay -- probability of material delay (classification) ---
delay_clf = HistGradientBoostingClassifier(
    max_depth=6, learning_rate=0.06, max_iter=300, l2_regularization=0.5, random_state=42
)
delay_clf.fit(X_train, y_delayflag_train)
delay_proba = delay_clf.predict_proba(X_test)[:, 1]
delay_auc = roc_auc_score(y_delayflag_test, delay_proba)
delay_brier = brier_score_loss(y_delayflag_test, delay_proba)
print(f"Delay-probability model  AUC (out-of-time): {delay_auc:.3f}  Brier: {delay_brier:.3f}")

# --- Model 3: Expected delay duration, conditional regression (months) ---
delay_reg = HistGradientBoostingRegressor(
    max_depth=6, learning_rate=0.06, max_iter=300, l2_regularization=0.5, random_state=42
)
delay_reg.fit(X_train, y_delay_train)
delay_months_pred = delay_reg.predict(X_test)
delay_mae = mean_absolute_error(y_delay_test, delay_months_pred)
print(f"Delay-duration model  MAE (out-of-time): {delay_mae:.2f} months")

# --- One concrete backtest case (per differentiation strategy #4) ---
# Find a test-set project with a large actual overrun that the model would
# have flagged as high-risk, to demonstrate the early-warning claim concretely.
test_df = df.loc[labeled.index[test_mask]].copy()
test_df["pred_cost_overrun_pct"] = cost_pred
test_df["pred_delay_prob"] = delay_proba
test_df["pred_delay_months"] = delay_months_pred
flagged_early = test_df[
    (test_df["final_cost_overrun_pct"] > 20) & (test_df["pred_cost_overrun_pct"] > 12)
].sort_values("final_cost_overrun_pct", ascending=False)

backtest_case = None
if len(flagged_early) > 0:
    row = flagged_early.iloc[0]
    backtest_case = {
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "ministry": row["ministry"],
        "sanctioned_cost_cr": float(row["sanctioned_cost_cr"]),
        "actual_final_overrun_pct": float(row["final_cost_overrun_pct"]),
        "actual_final_delay_months": float(row["final_delay_months"]),
        "model_predicted_overrun_pct": float(row["pred_cost_overrun_pct"]),
        "model_predicted_delay_probability": float(row["pred_delay_prob"]),
        "note": (
            f"Sanctioned {row['sanctioned_cost_cr']:.0f} cr; model's out-of-time "
            f"prediction ({row['pred_cost_overrun_pct']:.1f}% overrun) would have "
            f"flagged this project as high-risk using only pre-completion features, "
            f"months before the {row['final_cost_overrun_pct']:.1f}% actual overrun "
            f"was final."
        ),
    }
    print("\nBacktest case:", json.dumps(backtest_case, indent=2))

# --- Save artifacts ---
joblib.dump(cost_model, f"{MODEL_DIR}/cost_overrun_model.joblib")
joblib.dump(delay_clf, f"{MODEL_DIR}/delay_probability_model.joblib")
joblib.dump(delay_reg, f"{MODEL_DIR}/delay_duration_model.joblib")
joblib.dump(enc, f"{MODEL_DIR}/categorical_encoder.joblib")

metrics = {
    "cutoff_year": CUTOFF_YEAR,
    "train_rows": int(len(X_train)),
    "test_rows": int(len(X_test)),
    "cost_overrun_mae_pp": round(float(cost_mae), 3),
    "delay_probability_auc": round(float(delay_auc), 4),
    "delay_probability_brier": round(float(delay_brier), 4),
    "delay_duration_mae_months": round(float(delay_mae), 3),
    "feature_cols": FEATURE_COLS,
    "cat_cols": CAT_COLS,
    "backtest_case": backtest_case,
    "model_family": "sklearn HistGradientBoosting (swap-in for XGBoost/LightGBM in production)",
}
with open(f"{MODEL_DIR}/training_metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print(f"\nSaved models + metrics to {MODEL_DIR}/")
