import re

filepath = "C:/paimana 03/frontend/src/App.jsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the synchronous recomputed assignment with state and useEffect
target_code = """  const recomputed = whatIfActive ? computeRiskConfidence(simulatedRow, normalization) : null;
  const recomputedStyle = recomputed ? actionStyle(recomputed.institutional_action) : null;
  const riskDelta = recomputed ? Math.round((recomputed.risk_score - (project.risk_score || 0)) * 10) / 10 : 0;"""

new_code = """  const [recomputed, setRecomputed] = useState(null);
  useEffect(() => {
    if (!whatIfActive) {
      setRecomputed(null);
      return;
    }
    const simulate = async () => {
      try {
        const res = await apiFetch(`/projects/${project.project_id}/simulate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            land_acquisition_status: simLand,
            approval_delay_months: simApproval,
            contractor_track_record_score: simContractor,
            consecutive_missed_cycles: simMissed,
          })
        });
        if (res.ok) {
          const data = await res.json();
          setRecomputed(data);
        }
      } catch (err) {
        console.error("Simulation failed", err);
      }
    };
    simulate();
  }, [whatIfActive, simLand, simApproval, simContractor, simMissed, project.project_id]);

  const recomputedStyle = recomputed ? actionStyle(recomputed.institutional_action) : null;
  const riskDelta = recomputed ? Math.round((recomputed.risk_score - (project.risk_score || 0)) * 10) / 10 : 0;
  
  // Use recomputed attribution if available
  const displayShapFactors = recomputed?.attribution_factors || shapFactors;
"""

content = content.replace(target_code, new_code)

# Replace 'shapFactors' mapped rendering with 'displayShapFactors'
content = content.replace("shapFactors.slice(0, 6).map((factor, idx)", "displayShapFactors.slice(0, 6).map((factor, idx)")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("App.jsx updated with simulator API call.")
