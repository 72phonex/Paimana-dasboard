# PAIMANA Early-Warning Ledger

**Predictive Infrastructure Monitoring & Analytics**
*SIH 2026 Prototype by Team Quantumsyntax (MoSPI / IPMD Central Sector Projects)*

---

## What this prototype does NOT claim
> **IMPORTANT: Please read before evaluating this prototype.**
> 
> 1. **Data Authenticity:** The data used in this prototype is **synthetic and calibrated**. It does NOT contain real MoSPI or government project data.
> 2. **Real-world Accuracy:** The metrics displayed reflect the performance of the model on the synthetic dataset, not real-world deployment performance.
> 3. **Decision Making:** This system is a **Decision-Support Recommendation** tool. It does NOT replace government decision-makers, nor does it automate policy actions.
> 4. **Confidence Interpretation:** "Evidence Confidence" is a heuristic reflecting data freshness and completeness. It is **not** the statistical probability that the model's prediction is correct.

---

## 1. Project Overview & SIH Alignment

PAIMANA addresses the problem of cost overruns and severe schedule delays in Central Sector Projects. It ingests monthly project status reports (like flash reports or tabular datasets), scores them for risk using machine learning, and flags projects requiring immediate institutional attention (e.g., PRAGATI, PMG).

## 2. Architecture

- **Frontend:** React + Vite (Vanilla CSS for lightweight styling)
- **Backend:** FastAPI (Python)
- **Database:** SQLite (Structured for seamless PostgreSQL migration in production)
- **ML Pipeline:** Scikit-learn (HistGradientBoosting)

## 3. Key Features

- **Predictive Risk Scoring:** Forecasts final cost overrun and material delay using point-in-time features.
- **Explainability:** Decomposes the risk score into independent contributing factors using baseline ablation techniques (Feature Attribution).
- **Interactive Simulator:** Allows decision-makers to perform "What-If" counterfactuals (e.g., what if the contractor is changed?) and see real-time recalculations.
- **Institutional Action Engine:** Deterministically maps ML risk scores and data confidence into actionable recommendations.
- **Admin Console:** Batch ingestion, validation, and on-the-fly model retraining.

## 4. Methodology & Data Honesty

### ML Methodology & Leakage Prevention
To ensure genuine "early-warning" capabilities, the model is trained strictly on **point-in-time** snapshots. 
- Features represent what was known at month *T* (e.g., intermediate progress, cost revisions to date).
- The final outcomes (e.g., final delay, final cost) are isolated purely as training labels.
- **Temporal Validation:** The model is trained on older projects (sanctioned before 2019) and validated on newer projects, preventing leakage of future institutional knowledge.

### Risk & Evidence Confidence
- **Risk Score:** A synthesized metric [0-10] aggregating predicted cost overrun, predicted delay duration, and delay probability.
- **Evidence Confidence:** A score reflecting data quality. A project missing reporting cycles for 4 months has low Evidence Confidence, even if its apparent risk is low.

## 5. Setup & Demo Instructions

### Clean Windows Setup

1. **Prerequisites:** 
   - Node.js (for `npm`)
   - Python 3.8+ (ensure it is accessible via the `python` command)
2. **Install Backend Dependencies:**
   ```cmd
   cd "C:\path\to\paimana"
   pip install -r backend/requirements.txt
   ```
3. **Start the Application:**
   ```cmd
   npm install
   npm run dev
   ```
   *(This starts both the Vite frontend and the FastAPI backend concurrently).*

### Hero Demo Workflow

1. Navigate to the **Executive Ledger**.
2. Select a project (e.g., one flagged for PMG Escalation).
3. Observe the **Risk Score** and **Evidence Confidence** indicators.
4. Review the **Feature Attribution Waterfall** to explain the primary drivers of risk.
5. Open the **Interactive "What-If" Counterfactual Simulator**.
6. Adjust the "Approval Delay" or "Contractor Score" and observe the live API recalculate the risk and update the recommended institutional action.

## 6. Production Scaling Roadmap

- **Database:** Migrate SQLite to PostgreSQL using the existing ANSI-standard schema.
- **Model:** Swap Scikit-learn HistGradientBoosting for distributed LightGBM or XGBoost (API compatible).
- **Authentication:** Add SSO/OAuth for government personnel roles.
