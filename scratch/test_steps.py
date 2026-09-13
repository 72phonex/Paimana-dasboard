import sys, os
from pathlib import Path

print("Step 1: Adding DLL dirs...", flush=True)
user_site = Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages"
if user_site.exists():
    for libs_dir in user_site.glob("*.libs"):
        if libs_dir.is_dir():
            try:
                os.add_dll_directory(str(libs_dir))
                print(f"Added DLL directory: {libs_dir.name}", flush=True)
            except Exception as e:
                print(f"Failed to add {libs_dir}: {e}", flush=True)

print("Step 2: Importing joblib...", flush=True)
import joblib
print("Joblib imported.", flush=True)

print("Step 3: Importing sklearn...", flush=True)
import sklearn
print("Sklearn imported.", flush=True)

print("Step 4: Importing HistGradientBoosting...", flush=True)
from sklearn.ensemble import HistGradientBoostingRegressor
print("HistGradientBoostingRegressor imported.", flush=True)
