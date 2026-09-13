"""
Adaptive, Format-Agnostic Ingestion Engine for MoSPI Flash Reports & Datasets.
Team Quantumsyntax — SIH 2026 (MoSPI/IPMD Central Sector Projects).

Solves year-over-year format churn in MoSPI publications:
- Layout-Agnostic Table Detection (does not depend on hardcoded Table 6 headers)
- Semantic Slot-Filling (extracts dates, costs, progress, agencies, and states irrespective of column ordering)
- CSV / Excel Dataset Ingestion with Fuzzy Column Mapping
- Automatic Fallback Architecture across format generations (2018-2026+)
"""

import csv
import json
import re
import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Fix Windows DLL loading for Python 3.8+ and 3.14 (scipy.libs, numpy.libs, pandas.libs)
user_site = Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages"
if user_site.exists():
    for libs_dir in user_site.glob("*.libs"):
        if libs_dir.is_dir():
            try:
                os.add_dll_directory(str(libs_dir))
            except Exception:
                pass

import numpy as np
import pandas as pd
import pypdf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scoring"))
sys.path.insert(0, str(ROOT / "pipeline"))
import score_lib as sl

ALL_INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Jammu and Kashmir", "Ladakh", "Delhi", "Puducherry", "Chandigarh", "Multi State", "Central"
]

STATE_TO_REGION = {
    "Andhra Pradesh": "South", "Telangana": "South", "Karnataka": "South",
    "Kerala": "South", "Tamil Nadu": "South", "Puducherry": "South",
    "Maharashtra": "West", "Gujarat": "West", "Goa": "West",
    "Bihar": "East", "Jharkhand": "East", "Odisha": "East", "West Bengal": "East",
    "Madhya Pradesh": "Central", "Chhattisgarh": "Central",
    "Uttar Pradesh": "North", "Uttarakhand": "North", "Rajasthan": "North",
    "Punjab": "North", "Haryana": "North", "Himachal Pradesh": "North",
    "Jammu and Kashmir": "North", "Ladakh": "North", "Delhi": "North",
    "Chandigarh": "North",
    "Assam": "North-East", "Arunachal Pradesh": "North-East", "Manipur": "North-East",
    "Meghalaya": "North-East", "Mizoram": "North-East", "Nagaland": "North-East",
    "Sikkim": "North-East", "Tripura": "North-East",
}

MONTH_MAP = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def normalize_month_year(d_str: str) -> Optional[Tuple[int, int]]:
    if not d_str or str(d_str).strip() in ["NA", "-", "(-)", "None", ""]:
        return None
    cleaned = str(d_str).strip("()").strip()
    
    # 1. MM/YYYY or DD/MM/YYYY
    m = re.search(r"\b(\d{1,2})/(\d{4})\b", cleaned)
    if m:
        return int(m.group(1)), int(m.group(2))
    
    m_full = re.search(r"\b\d{1,2}/\d{1,2}/(\d{4})\b", cleaned)
    if m_full:
        parts = cleaned.split("/")
        return int(parts[1]), int(m_full.group(1))

    # 2. Mon-YYYY or Month YYYY (e.g. March 2023, Mar-2022)
    m_alpha = re.search(r"([A-Za-z]{3,9})[-/\s]+(\d{4})", cleaned)
    if m_alpha:
        m_name = m_alpha.group(1).upper()[:3]
        if m_name in MONTH_MAP:
            return MONTH_MAP[m_name], int(m_alpha.group(2))

    return None


def calculate_months_diff(start_my: Optional[Tuple[int, int]], end_my: Optional[Tuple[int, int]]) -> float:
    if not start_my or not end_my:
        return 0.0
    return max(0.0, float((end_my[1] - start_my[1]) * 12 + (end_my[0] - start_my[0])))


# ---------------------------------------------------------------------------
# Strategy 2: Adaptive Semantic Slot-Filling Parser for Non-Standard PDFs
# ---------------------------------------------------------------------------
def extract_semantic_projects_from_pdf(pdf_path: Path) -> Tuple[str, int, int, List[Dict[str, Any]]]:
    """
    Extracts projects by analyzing semantic text blocks rather than fixed column coordinates.
    Works across 2020-2025 OCMS and older MoSPI bulletins with altered column ordering.
    """
    reader = pypdf.PdfReader(str(pdf_path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    num_pages = len(page_texts)

    # 1. Detect Report Month & Year
    report_month_name = "June"
    report_year = 2026
    for i in range(min(10, num_pages)):
        txt = page_texts[i]
        m = re.search(r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})", txt, re.IGNORECASE)
        if m:
            report_month_name = m.group(1).capitalize()
            report_year = int(m.group(2))
            break

    report_as_of = f"{report_month_name} {report_year}"
    report_month_num = MONTH_MAP.get(report_month_name.upper(), 6)

    # 2. Find table density candidate pages
    candidate_pages = []
    for i in range(num_pages):
        txt = page_texts[i]
        # Signals of a project table page
        has_dates = bool(re.search(r"\b\d{1,2}/\d{4}\b", txt)) or bool(re.search(r"\b(201\d|202\d)\b", txt))
        has_monetary = bool(re.search(r"\b\d{2,6}\.\d{1,2}\b", txt)) or ("Crore" in txt or "Cost" in txt)
        has_keyword = any(k in txt for k in ["Project", "Agency", "Expenditure", "DoC", "Approval", "Progress", "Sl.No", "Sl. No"])
        if has_dates and has_monetary and has_keyword:
            candidate_pages.append(i)

    if not candidate_pages:
        candidate_pages = list(range(max(0, num_pages - 100), num_pages))

    # 3. Group candidate lines into project blocks
    blocks = []
    curr_block = []
    curr_ministry = "Road Transport & Highways"
    curr_sector = "Roads"

    for p in candidate_pages:
        page_text = page_texts[p]
        lines = page_text.split("\n")
        
        for l in lines:
            ls = l.strip()
            if not ls:
                continue
            
            # Skip common running headers & footers
            if ls.startswith("Page ") or "For details visit" in ls or "PAIMANA" in ls or ls.startswith("Total (") or ls.startswith("Total("):
                continue
            if ls in ["Sl.No", "Sl. No", "Project Name", "(Agency)", "State", "Date of Approval", "MM/YYYY", "Cost", "Expenditure"]:
                continue
                
            if ls.startswith("Ministry of ") or ls.startswith("Department of "):
                curr_ministry = ls.replace("Ministry of ", "").replace("Department of ", "").strip()
                continue
                
            # Block delimiter: line is an integer serial number <= 4000 or starts with PAI-
            if (re.match(r"^\d{1,4}\.?$", ls) and int(ls.rstrip(".")) < 4000) or re.match(r"^PAI-\d+", ls):
                if curr_block and len(curr_block) >= 3:
                    blocks.append({"lines": curr_block, "ministry": curr_ministry, "sector": curr_sector})
                curr_block = [ls]
            elif curr_block:
                curr_block.append(ls)

    if curr_block and len(curr_block) >= 3:
        blocks.append({"lines": curr_block, "ministry": curr_ministry, "sector": curr_sector})

    # 4. Semantic slot-filling for each block
    extracted_records = []
    for idx, b in enumerate(blocks):
        lines = b["lines"]
        full_text = " ".join(lines)
        
        sl_str = lines[0].rstrip(".")
        
        # A. Agency extraction
        agency_m = re.search(r"\(([A-Za-z0-9\s\[\]\.\-]{2,25})\)", full_text)
        agency = agency_m.group(1) if agency_m else ""

        # B. Project code extraction
        code_m = re.search(r"\((\d{5,8})\)", full_text)
        project_code = code_m.group(1) if code_m else f"{int(sl_str) if sl_str.isdigit() else idx+1:05d}"
        project_id = f"PAI-{project_code}"

        # C. State extraction
        found_state = "Delhi"
        for st in ALL_INDIAN_STATES:
            if re.search(r"\b" + re.escape(st) + r"\b", full_text):
                found_state = st
                break

        # D. Project Name extraction (lines before code/state)
        name_parts = []
        for l in lines[1:]:
            if l.startswith("(") and l.endswith(")"):
                continue
            if re.search(r"\b\d{1,2}/\d{4}\b", l) or re.search(r"\b\d{2,6}\.\d{1,2}\b", l):
                break
            if l == found_state:
                break
            name_parts.append(l)
        
        project_name = " ".join(name_parts) or f"{b['sector']} Project {sl_str}"

        # E. Dates extraction (all dates in block)
        date_matches = re.findall(r"\b(\d{1,2}/\d{4})\b", full_text)
        app_my, start_my, odoc_my, rdoc_my = None, None, None, None
        
        if len(date_matches) >= 4:
            app_my = normalize_month_year(date_matches[0])
            start_my = normalize_month_year(date_matches[1])
            odoc_my = normalize_month_year(date_matches[2])
            rdoc_my = normalize_month_year(date_matches[3])
        elif len(date_matches) == 3:
            app_my = normalize_month_year(date_matches[0])
            odoc_my = normalize_month_year(date_matches[1])
            rdoc_my = normalize_month_year(date_matches[2])
        elif len(date_matches) == 2:
            app_my = normalize_month_year(date_matches[0])
            odoc_my = normalize_month_year(date_matches[1])
        elif len(date_matches) == 1:
            app_my = normalize_month_year(date_matches[0])

        # F. Monetary & Progress extraction
        # All decimal numbers in block
        numbers = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,6}\.\d{1,2}\b", full_text)]
        
        # Check for explicit progress with %
        prog_m = re.search(r"\b(\d{1,3}(?:\.\d{1,2})?)\s*%", full_text)
        physical_prog = float(prog_m.group(1)) if prog_m else 0.0

        orig_cost, rev_cost, expenditure = 0.0, 0.0, 0.0
        
        if not prog_m and numbers:
            # Often the last number <= 100 is physical progress
            if numbers[-1] <= 100.0 and len(numbers) >= 2:
                physical_prog = numbers[-1]
                numbers = numbers[:-1]

        if len(numbers) >= 3:
            orig_cost = numbers[0]
            rev_cost = numbers[1]
            expenditure = numbers[2]
        elif len(numbers) == 2:
            orig_cost = numbers[0]
            rev_cost = numbers[0]
            expenditure = numbers[1]
        elif len(numbers) == 1:
            orig_cost = numbers[0]
            rev_cost = numbers[0]

        if rev_cost == 0.0 and orig_cost > 0.0:
            rev_cost = orig_cost

        # G. Calculate derived metrics
        base_sanction_my = app_my or start_my or (1, report_year - 3)
        months_since_sanction = int(calculate_months_diff(base_sanction_my, (report_month_num, report_year)))
        if months_since_sanction <= 0:
            months_since_sanction = 18

        planned_duration_years = round(max(0.5, calculate_months_diff(base_sanction_my, odoc_my) / 12.0), 2) if (base_sanction_my and odoc_my) else 3.5
        approval_delay = round(calculate_months_diff(app_my, start_my), 1) if (app_my and start_my) else 0.0
        
        delay_months_hist = round(calculate_months_diff(odoc_my, rdoc_my), 1) if (odoc_my and rdoc_my) else 0.0
        cost_overrun_hist = round(((rev_cost - orig_cost) / max(1.0, orig_cost)) * 100.0, 2) if rev_cost > orig_cost else 0.0

        base_cost = rev_cost if rev_cost > 0 else orig_cost
        fin_prog = round(min(100.0, (expenditure / max(1.0, base_cost)) * 100.0), 1)
        phys_prog = round(min(100.0, max(0.0, physical_prog)), 1)

        project_stage = "pre_construction" if phys_prog < 15.0 else "construction"
        land_status = "complete" if project_stage == "construction" else ("not_started" if phys_prog == 0 else "partial")
        
        missed_cycles = 4 if (phys_prog == 0 and months_since_sanction >= 24) else 0
        last_report = 4 if missed_cycles >= 3 else 0

        contractor_score = 0.48 if (delay_months_hist > 12 or cost_overrun_hist > 20) else (0.62 if (delay_months_hist > 0 or cost_overrun_hist > 0) else 0.82)

        record = {
            "project_id": project_id,
            "project_name": project_name,
            "agency": agency,
            "project_code": project_code,
            "state": found_state,
            "approval_date": f"{app_my[0]:02d}/{app_my[1]}" if app_my else "",
            "start_date": f"{start_my[0]:02d}/{start_my[1]}" if start_my else "",
            "original_doc": f"{odoc_my[0]:02d}/{odoc_my[1]}" if odoc_my else "",
            "revised_doc": f"{rdoc_my[0]:02d}/{rdoc_my[1]}" if rdoc_my else "",
            "ministry": b["ministry"],
            "sector": b["sector"],
            "region": STATE_TO_REGION.get(found_state, "North"),
            "sanction_date": f"{base_sanction_my[1]:04d}-{base_sanction_my[0]:02d}-01",
            "sanctioned_cost_cr": round(orig_cost, 2),
            "revised_cost_cr": round(rev_cost, 2),
            "cumulative_expenditure_cr": round(expenditure, 2),
            "physical_progress_pct": phys_prog,
            "financial_progress_pct": fin_prog,
            "project_stage": project_stage,
            "land_acquisition_status": land_status,
            "months_since_last_report": last_report,
            "consecutive_missed_cycles": missed_cycles,
            "planned_duration_years": planned_duration_years,
            "months_since_sanction": months_since_sanction,
            "cost_revisions_count": 1 if (rev_cost > orig_cost * 1.01) else 0,
            "approval_delay_months": approval_delay,
            "delay_months_historical": delay_months_hist,
            "cost_overrun_historical": cost_overrun_hist,
            "financing_irregularity_flag": 1 if (fin_prog > phys_prog + 25.0) else 0,
            "contractor_track_record_score": contractor_score,
            "ministry_reporting_compliance_rate": 0.88,
            "evidence_completeness_score": round(
                0.30 * bool(project_name) +
                0.15 * bool(agency) +
                0.10 * bool(project_code) +
                0.15 * bool(found_state) +
                0.20 * min(len(date_matches), 4) / 4.0 +
                0.10 * bool(numbers), 3
            ),
            "data_provenance": "MoSPI Flash Report adaptive semantic extraction",
        }
        extracted_records.append(record)

    return report_as_of, report_month_num, report_year, extracted_records


# ---------------------------------------------------------------------------
# Strategy 3: Direct CSV Ingestion Engine with Fuzzy Column Mapping
# ---------------------------------------------------------------------------
def extract_projects_from_csv(csv_path: Path) -> Tuple[str, int, int, List[Dict[str, Any]]]:
    """
    Ingests CSV project datasets from any MoSPI export or spreadsheet with fuzzy column mapping.
    """
    encodings = ["utf-8", "latin1", "cp1252", "iso-8859-1"]
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            break
        except Exception:
            continue

    if df is None:
        raise ValueError(f"Could not read CSV file {csv_path.name} with standard encodings.")

    # Normalize column names with fuzzy matching
    col_map = {}
    for col in df.columns:
        c = str(col).strip().lower().replace("_", " ")
        if any(k in c for k in ["project name", "name of project", "work name", "project"]):
            col_map.setdefault("project_name", col)
        elif any(k in c for k in ["original cost", "sanctioned cost", "orig cost", "cost orig", "estimated cost"]):
            col_map.setdefault("sanctioned_cost_cr", col)
        elif any(k in c for k in ["revised cost", "anticipated cost", "rev cost", "latest cost"]):
            col_map.setdefault("revised_cost_cr", col)
        elif "cost" in c and "sanctioned_cost_cr" not in col_map:
            col_map.setdefault("sanctioned_cost_cr", col)
        elif any(k in c for k in ["cumulative expenditure", "expenditure", "exp"]):
            col_map.setdefault("cumulative_expenditure_cr", col)
        elif any(k in c for k in ["physical progress", "progress (%)", "progress"]):
            col_map.setdefault("physical_progress_pct", col)
        elif "ministry" in c:
            col_map.setdefault("ministry", col)
        elif "sector" in c:
            col_map.setdefault("sector", col)
        elif "state" in c or "location" in c:
            col_map.setdefault("state", col)
        elif "agency" in c:
            col_map.setdefault("agency", col)
        elif "code" in c or "id" in c:
            col_map.setdefault("project_id", col)

    records = []
    for idx, row in df.iterrows():
        p_name = str(row.get(col_map.get("project_name", ""), f"Project {idx+1}")).strip()
        p_id = str(row.get(col_map.get("project_id", ""), f"PAI-{idx+1:05d}")).strip()
        if not p_id.startswith("PAI-"):
            p_id = f"PAI-{p_id}"
            
        ministry = str(row.get(col_map.get("ministry", ""), "Road Transport & Highways")).strip()
        sector = str(row.get(col_map.get("sector", ""), "Roads")).strip()
        state = str(row.get(col_map.get("state", ""), "Delhi")).strip()
        agency = str(row.get(col_map.get("agency", ""), "")).strip()

        try:
            orig_cost = float(str(row.get(col_map.get("sanctioned_cost_cr", 0), 0)).replace(",", ""))
        except Exception:
            orig_cost = 100.0

        try:
            rev_cost = float(str(row.get(col_map.get("revised_cost_cr", orig_cost), orig_cost)).replace(",", ""))
        except Exception:
            rev_cost = orig_cost

        try:
            expenditure = float(str(row.get(col_map.get("cumulative_expenditure_cr", 0), 0)).replace(",", ""))
        except Exception:
            expenditure = 0.0

        try:
            phys_prog = float(str(row.get(col_map.get("physical_progress_pct", 0), 0)).replace("%", "").replace(",", ""))
        except Exception:
            phys_prog = 0.0

        base_cost = rev_cost if rev_cost > 0 else orig_cost
        fin_prog = round(min(100.0, (expenditure / max(1.0, base_cost)) * 100.0), 1)

        project_stage = "pre_construction" if phys_prog < 15.0 else "construction"
        land_status = "complete" if project_stage == "construction" else ("not_started" if phys_prog == 0 else "partial")

        records.append({
            "project_id": p_id,
            "project_name": p_name,
            "agency": agency,
            "ministry": ministry,
            "sector": sector,
            "state": state,
            "region": STATE_TO_REGION.get(state, "North"),
            "sanction_date": "2023-01-01",
            "sanctioned_cost_cr": round(orig_cost, 2),
            "revised_cost_cr": round(rev_cost, 2),
            "cumulative_expenditure_cr": round(expenditure, 2),
            "physical_progress_pct": round(phys_prog, 1),
            "financial_progress_pct": fin_prog,
            "project_stage": project_stage,
            "land_acquisition_status": land_status,
            "months_since_last_report": 0,
            "consecutive_missed_cycles": 0,
            "planned_duration_years": 3.5,
            "months_since_sanction": 36,
            "cost_revisions_count": 1 if (rev_cost > orig_cost * 1.01) else 0,
            "approval_delay_months": 0.0,
            "delay_months_historical": 0.0,
            "cost_overrun_historical": round(((rev_cost - orig_cost) / max(1.0, orig_cost)) * 100.0, 2) if rev_cost > orig_cost else 0.0,
            "financing_irregularity_flag": 1 if (fin_prog > phys_prog + 25.0) else 0,
            "contractor_track_record_score": 0.70,
            "ministry_reporting_compliance_rate": 0.88,
            "evidence_completeness_score": round(
                sum(k in col_map for k in [
                    "project_name", "sanctioned_cost_cr", "revised_cost_cr",
                    "cumulative_expenditure_cr", "physical_progress_pct",
                    "ministry", "sector", "state", "agency", "project_id"
                ]) / 10.0, 3
            ),
            "data_provenance": "Direct CSV dataset import",
        })

    report_as_of = csv_path.stem.replace("_", " ").title()
    return report_as_of, 6, 2026, records
