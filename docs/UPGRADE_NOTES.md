# PAIMANA ingestion & confidence upgrade

## What changed

### 1. Background PDF ingestion
The admin upload endpoint now stages files and returns an ingestion `job_id` immediately. Heavy PDF parsing, extraction and ML scoring run in a bounded background worker pool.

Frontend polling reads `/api/admin/ingestion/{job_id}` so the progress bar reflects real processing stages instead of timer-only simulated progress.

### 2. Duplicate detection
Each upload is SHA-256 hashed while staging. Re-uploading the same document reuses the existing scored dataset instead of parsing and scoring it again.

### 3. Faster parsing / scoring
PDF page text is extracted once per document and reused by the parser. Scoring assets are cached in-process, and the batch scorer uses the same vectorized scoring path as ingestion.

### 4. Evidence Confidence v2
Confidence is no longer driven mainly by reporting silence. It combines:

- 35% data completeness
- 15% data freshness
- 20% model certainty
- 15% internal consistency
- 15% prediction concordance across cost / delay signals

A non-linear quality transform prevents the portfolio from collapsing into a wall of 95–99% values. Each project also receives a `confidence_breakdown` explaining the score.

### 5. Honest missing-data handling
PDF/CSV parsing now records an `evidence_completeness_score` and `data_provenance`. Missing source fields are not silently treated as full evidence.

## Verification

- FastAPI app imports and compiles successfully.
- Real PDF upload test returned HTTP 200 and accepted the document in ~0.06 s on the test environment.
- A 1,981-project April 2026 PDF completed background extraction + vectorized ML scoring successfully.
- The upgraded seeded portfolio contains 1,999 ongoing projects with 504 distinct confidence values; min 27.5, median 76.1, mean 74.3, max 98.0.

## Run locally

```bash
npm install
npm run dev
```

The source application is the authoritative version. After installing dependencies on the target platform, `npm run build` regenerates `dist/` for deployment.
