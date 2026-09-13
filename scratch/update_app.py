import re

filepath = "C:/paimana 03/backend/app.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = """            scored = efr.extract_and_score_file(tmp_path)
            
            gen_month = scored.get("generated_at", file.filename.replace(ext, ""))"""

replacement = """            # Basic CSV validation (SIH robustness)
            if ext == ".csv":
                import pandas as pd
                try:
                    df_check = pd.read_csv(tmp_path)
                    req_cols = ["project_id", "project_name", "sanctioned_cost_cr"]
                    missing = [c for c in req_cols if c not in df_check.columns]
                    if missing:
                        raise ValueError(f"Missing required columns: {missing}")
                    if "physical_progress_pct" in df_check.columns:
                        invalid_pct = df_check[(df_check.physical_progress_pct < 0) | (df_check.physical_progress_pct > 100)]
                        if not invalid_pct.empty:
                            raise ValueError(f"Found {len(invalid_pct)} rows with invalid physical_progress_pct (must be 0-100)")
                except Exception as csv_err:
                    raise HTTPException(422, f"CSV Validation failed for {file.filename}: {str(csv_err)}")

            scored = efr.extract_and_score_file(tmp_path)
            
            gen_month = scored.get("generated_at", file.filename.replace(ext, ""))"""

content = content.replace(target, replacement)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated app.py with CSV validation.")
