# SIH Judge Q&A

**1. Is this real data?**
No. This prototype uses synthetic, calibrated data to simulate Central Sector Projects. It is strictly for demonstration purposes. We explicitly denote this with a persistent "DEMO MODE" banner to avoid misleading claims.

**2. How do you prevent data leakage?**
We generate "point-in-time" snapshots for completed projects. This means we artificially roll back progress (e.g., from 100% to 45%) and proportionally scale down accumulated delays and cost revisions so that the model only trains on features that would genuinely be known midway through a project, separating the final cost/delay explicitly as the prediction target.

**3. Why ML instead of rules?**
While rules flag delays *after* they happen, ML identifies complex nonlinear patterns (e.g., specific contractor behavior coupled with land acquisition friction and minor early delays) to predict *future* failures months before they hit traditional reporting thresholds. 

**4. How do you explain predictions?**
We use Feature Attribution based on baseline ablation. For each prediction, the system decomposes the risk score by measuring how much each specific feature (e.g., "Approval Lag") deviates the risk from the baseline. 

**5. What does confidence mean?**
"Evidence Confidence" measures the freshness and completeness of the data for a given project (e.g., missing reporting cycles reduce confidence). It is a data-quality heuristic, *not* the statistical probability that the ML prediction is correct. 

**6. How early can you detect a failing project?**
With temporal point-in-time validation, we demonstrate the ability to flag a project for escalation months before the final delay is formally recognized in the completion report.

**7. What happens if reporting is missing?**
The model factors in `consecutive_missed_cycles` as a feature itself, often treating it as a risk signal. However, it also lowers the "Evidence Confidence" score, ensuring human decision-makers know they are looking at stale data and might recommend an audit before drastic escalation.

**8. What happens if the model is wrong?**
The system is explicitly designed as a "Decision-Support Recommendation" engine. It never automatically executes policy. If the model is wrong, the institutional action (e.g., PMG escalation) just results in a human review where the discrepancy is caught.

**9. How does this scale nationally?**
The backend API is designed statelessly. The SQLite database uses an ANSI-standard schema that directly maps to PostgreSQL for production. 

**10. What happens with bad PDF/CSV data?**
The ingestion pipeline strictly validates data bounds (e.g., physical progress must be 0-100%). Invalid files or missing required columns are rejected with HTTP 422 validation reports rather than silently corrupting the database.
