import urllib.request
import json
import mimetypes
import uuid
from pathlib import Path

# Create a multipart/form-data upload test using one of the existing CSVs or creating a small test CSV
test_csv_content = """sl,project_name,agency,project_code,legacy_code,pmgid,state,approval_date,start_date,orig_doc,revised_doc,original_cost,revised_cost,expenditure,physical_progress
1,Varanasi Multi-Modal Freight Terminal,IWAI,IWAI-2026-01,LEG-01,PMG-01,Uttar Pradesh,04/2021,06/2021,12/2024,06/2025,450.0,520.0,380.0,85.0
2,Bhopal Ring Expressway Phase 2,NHAI,NHAI-2026-99,LEG-02,PMG-02,Madhya Pradesh,01/2022,03/2022,03/2025,12/2025,890.0,980.0,610.0,68.0
"""

boundary = uuid.uuid4().hex
body = []

body.append(f"--{boundary}".encode())
body.append(b'Content-Disposition: form-data; name="purpose"')
body.append(b'')
body.append(b'prediction')

body.append(f"--{boundary}".encode())
body.append(b'Content-Disposition: form-data; name="files"; filename="Test_MoSPI_Ingestion.csv"')
body.append(b'Content-Type: text/csv')
body.append(b'')
body.append(test_csv_content.strip().encode())

body.append(f"--{boundary}--".encode())
body.append(b'')

payload = b"\r\n".join(body)

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/admin/upload-multiple",
    data=payload,
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload))
    },
    method="POST"
)

res = urllib.request.urlopen(req)
data = json.loads(res.read().decode())
print("Upload Multiple response:", json.dumps(data, indent=2))
