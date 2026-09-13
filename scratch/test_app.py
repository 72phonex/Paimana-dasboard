import sys, os
from pathlib import Path

# Fix Windows DLL loading for Python 3.14 user site-packages (scipy.libs, numpy.libs, pandas.libs)
user_site = Path(os.environ.get("APPDATA", "")) / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "site-packages"
if user_site.exists():
    for libs_dir in user_site.glob("*.libs"):
        if libs_dir.is_dir():
            try:
                os.add_dll_directory(str(libs_dir))
                print(f"Added DLL directory: {libs_dir}")
            except Exception as e:
                print(f"Failed to add {libs_dir}: {e}")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scoring"))
sys.path.insert(0, str(ROOT / "pipeline"))

print("Testing import app...")
import app
print("app imported successfully!")
