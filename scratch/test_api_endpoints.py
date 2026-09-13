import urllib.request
import json
import sys

BASE = "http://127.0.0.1:8000"

def get(path):
    req = urllib.request.urlopen(f"{BASE}{path}")
    data = json.loads(req.read().decode())
    print(f"GET {path} -> HTTP {req.status}, Keys/Count: {len(data) if isinstance(data, list) else list(data.keys())[:4]}")
    return data

def post(path, payload=None):
    body = json.dumps(payload).encode() if payload else b""
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"}, method="POST")
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    print(f"POST {path} -> HTTP {res.status}, Status: {data.get('status')}")
    return data

def patch(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"}, method="PATCH")
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    print(f"PATCH {path} -> HTTP {res.status}, Status: {data.get('status')}")
    return data

print("--- Testing PAIMANA Backend Endpoints ---")
try:
    get("/health")
    reports = get("/api/admin/reports")
    print(f"Total reports in registry: {len(reports)}")
    for r in reports:
        print(f"  - {r['id']}: {r['title']} ({r.get('project_count', 0)} projs, purpose={r.get('purpose')}, active={r.get('is_active')})")
    
    get("/api/admin/metrics")
    get("/reports/june_2026")
    
    # Test Patch
    first_id = reports[0]["id"]
    patch(f"/api/admin/reports/{first_id}", {"purpose": "prediction"})
    
    # Test Predict/Rescore
    post(f"/api/admin/predict/{first_id}")
    
    # Test Retrain
    train_res = post("/api/admin/train")
    print(f"Retrained metrics: Cost MAE={train_res['metrics']['cost_overrun_mae_pp']}, Delay AUC={train_res['metrics']['delay_probability_auc']}")

    print("\nALL API ENDPOINTS TESTED AND WORKING PERFECTLY!")
except Exception as e:
    print(f"\nERROR: {e}")
    sys.exit(1)
