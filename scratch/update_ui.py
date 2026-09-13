import re

filepath = "C:/paimana 03/frontend/src/App.jsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Tree-SHAP -> Feature Attribution (Baseline Ablation)
content = re.sub(r'Tree-SHAP Feature Attribution Waterfall', 'Feature Attribution (Baseline Ablation)', content)
content = re.sub(r'Tree-SHAP Feature Attribution', 'Feature Attribution (Baseline Ablation)', content)
content = re.sub(r'Tree SHAP Feature Attribution', 'Feature Attribution (Baseline Ablation)', content)
content = re.sub(r'Tree-SHAP', 'Feature Attribution', content)

# 2. Confidence -> Evidence Confidence
content = re.sub(r'Data Confidence', 'Evidence Confidence', content)
content = re.sub(r'>Confidence<', '>Evidence Confidence<', content)
content = re.sub(r'CONFIDENCE', 'EVIDENCE CONFIDENCE', content)
content = re.sub(r'Low Confidence Audit', 'Low Evidence Confidence Audit', content)

# 3. Add tooltip to Evidence Confidence (just replace the Data Confidence label with a tooltip span)
content = content.replace(
    '<span>Evidence Confidence</span>', 
    '<span title="Evidence Confidence reflects the freshness and completeness of available project evidence. It is not the probability that the model prediction is correct.">Evidence Confidence</span>'
)

# 4. Remove fake static precision from the trajectories
content = re.sub(r'±1\.5 pts', '', content)
content = re.sub(r'\+16\.8 pts', '', content)
content = re.sub(r'\-14\.2 pts', '', content)
content = re.sub(r'\+6\.1 pts', '', content)

# 5. DEMO MODE banner in the header
banner_html = """
        {/* DEMO MODE BANNER */}
        <div style={{ background: T.brick, color: '#fff', fontSize: 11, fontWeight: 600, textAlign: 'center', padding: '4px', letterSpacing: 1 }}>
          DEMO MODE • SYNTHETIC + CALIBRATED DATA
        </div>
"""
content = content.replace('      {/* Top Banner (Header) */}', banner_html + '\n      {/* Top Banner (Header) */}')

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("App.jsx updated successfully.")
