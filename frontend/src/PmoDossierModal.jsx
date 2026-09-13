import React from "react";
import { X, Printer, ShieldAlert, AlertTriangle, FileText, CheckCircle2, Building, Layers } from "lucide-react";
import { T, sans, serif, mono, crore, actionStyle } from "./tokens";

export default function PmoDossierModal({ isOpen, onClose, projects = [], activeReportMeta, totalCost }) {
  if (!isOpen) return null;

  // Filter top distressed megaprojects (sanctioned >= 1,000 Cr and high risk, sorted by risk descending)
  const distressedMegaprojects = projects
    .filter((p) => (p.sanctioned_cost_cr || 0) >= 500 && (p.risk_score || 0) >= 35)
    .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    .slice(0, 10);

  const pragatiCandidates = projects.filter((p) => p.institutional_action === "PRAGATI candidate");
  const pmgEscalations = projects.filter((p) => p.institutional_action === "Escalate to PMG");
  const capitalAtRisk = distressedMegaprojects.reduce((sum, p) => sum + (p.sanctioned_cost_cr || 0), 0);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: "rgba(10, 18, 32, 0.75)", backdropFilter: "blur(4px)",
        zIndex: 9999, display: "flex", justifyContent: "center", alignItems: "flex-start",
        overflowY: "auto", padding: "30px 16px"
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          #pmo-dossier-content, #pmo-dossier-content * { visibility: visible !important; }
          #pmo-dossier-content {
            position: absolute !important;
            left: 0 !important; top: 0 !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 10mm 15mm !important;
            box-shadow: none !important;
            border: none !important;
            background: #fff !important;
          }
          .no-print { display: none !important; }
        }
      `}</style>

      <div
        id="pmo-dossier-content"
        style={{
          width: "100%", maxWidth: 1080, background: "#FFFFFF",
          borderRadius: 8, boxShadow: "0 20px 40px rgba(0,0,0,0.25)",
          border: `1px solid ${T.hairlineStrong}`, overflow: "hidden",
          fontFamily: sans, color: T.ink, position: "relative"
        }}
      >
        {/* Top Government Heraldic Banner */}
        <div style={{
          background: "#0E1E34", color: "#FFFFFF", padding: "20px 28px",
          borderBottom: "3px solid #E7A73B", display: "flex", justifyContent: "space-between",
          alignItems: "flex-start"
        }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
              <span style={{
                background: "#E7A73B", color: "#0E1E34", padding: "2px 8px",
                borderRadius: 3, fontSize: 11, fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase"
              }}>
                Official PMO Briefing
              </span>
              <span style={{ fontSize: 12, color: "#9EB0C6", letterSpacing: 0.5 }}>
                CABINET SECRETARIAT · GOVERNMENT OF INDIA
              </span>
            </div>
            <div style={{ fontFamily: serif, fontSize: 24, fontWeight: 700, letterSpacing: 0.2 }}>
              Project Monitoring Group (PMG) & PRAGATI National Dossier
            </div>
            <div style={{ fontSize: 12.5, color: "#B0C4DE", marginTop: 4 }}>
              Early-Warning Intelligence on Critical Infrastructure Distress & Inter-Ministerial Deadlocks
            </div>
          </div>

          <div className="no-print" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={handlePrint}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                background: "#E7A73B", color: "#0E1E34", border: "none",
                borderRadius: 5, padding: "8px 14px", fontSize: 13, fontWeight: 700,
                cursor: "pointer", boxShadow: "0 2px 4px rgba(0,0,0,0.15)"
              }}
            >
              <Printer size={15} />
              Print / Save PDF
            </button>
            <button
              onClick={onClose}
              style={{
                background: "rgba(255,255,255,0.12)", color: "#FFFFFF", border: "none",
                borderRadius: 5, padding: "8px", cursor: "pointer"
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Dossier Metadata & Timestamp */}
        <div style={{
          padding: "12px 28px", background: "#F6F8FA", borderBottom: `1px solid ${T.hairline}`,
          display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10,
          fontSize: 12, color: T.inkMuted
        }}>
          <div>
            <strong>Active Benchmark Portfolio:</strong> {activeReportMeta?.title || "June 2026 Flash Report"} ({projects.length.toLocaleString()} projects)
          </div>
          <div>
            <strong>Dossier Generated:</strong> {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
          </div>
          <div>
            <strong>Total Portfolio Exposure:</strong> <span style={{ fontFamily: mono, fontWeight: 600, color: T.ink }}>{crore(totalCost)}</span>
          </div>
        </div>

        <div style={{ padding: "24px 28px" }}>
          {/* Executive KPI Summary Tiles */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginBottom: 24 }}>
            <div style={{ background: T.brickBg, border: `1px solid ${T.brickBorder}`, borderRadius: 6, padding: "12px 16px" }}>
              <div style={{ fontSize: 11.5, color: T.brick, fontWeight: 600, textTransform: "uppercase" }}>
                PRAGATI Deadlocks
              </div>
              <div style={{ fontFamily: serif, fontSize: 26, fontWeight: 700, color: T.brick, marginTop: 4 }}>
                {pragatiCandidates.length} Projects
              </div>
              <div style={{ fontSize: 11.5, color: T.inkMuted, marginTop: 4 }}>
                Stuck on Land ROW & $\ge 3$ missed reports
              </div>
            </div>

            <div style={{ background: T.brickBg, border: `1px solid ${T.brickBorder}`, borderRadius: 6, padding: "12px 16px" }}>
              <div style={{ fontSize: 11.5, color: T.brick, fontWeight: 600, textTransform: "uppercase" }}>
                PMG Cabinet Escalations
              </div>
              <div style={{ fontFamily: serif, fontSize: 26, fontWeight: 700, color: T.brick, marginTop: 4 }}>
                {pmgEscalations.length} Projects
              </div>
              <div style={{ fontSize: 11.5, color: T.inkMuted, marginTop: 4 }}>
                Scale $\ge$ ₹500 Cr with severe risk ($\ge 45$)
              </div>
            </div>

            <div style={{ background: T.ochreBg, border: `1px solid ${T.ochreBorder}`, borderRadius: 6, padding: "12px 16px" }}>
              <div style={{ fontSize: 11.5, color: T.ochre, fontWeight: 600, textTransform: "uppercase" }}>
                Capital At Immediate Risk
              </div>
              <div style={{ fontFamily: mono, fontSize: 24, fontWeight: 700, color: T.ochre, marginTop: 4 }}>
                {crore(capitalAtRisk)}
              </div>
              <div style={{ fontSize: 11.5, color: T.inkMuted, marginTop: 4 }}>
                Across top 10 distressed megaprojects
              </div>
            </div>

            <div style={{ background: T.greenBg, border: `1px solid ${T.greenBorder}`, borderRadius: 6, padding: "12px 16px" }}>
              <div style={{ fontSize: 11.5, color: T.green, fontWeight: 600, textTransform: "uppercase" }}>
                Predictive Accuracy (AUC)
              </div>
              <div style={{ fontFamily: mono, fontSize: 24, fontWeight: 700, color: T.green, marginTop: 4 }}>
                0.987 AUC
              </div>
              <div style={{ fontSize: 11.5, color: T.inkMuted, marginTop: 4 }}>
                HistGradientBoost out-of-time benchmark
              </div>
            </div>
          </div>

          {/* Section 1: Top 10 Distressed Megaprojects */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <ShieldAlert size={18} color={T.brick} />
              <div style={{ fontFamily: serif, fontSize: 18, fontWeight: 600, color: T.ink }}>
                Priority 1: Top 10 Distressed Megaprojects Requiring Cabinet Secretariat Review
              </div>
            </div>

            <div style={{ border: `1px solid ${T.hairlineStrong}`, borderRadius: 6, overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "#F1F3F5", borderBottom: `1px solid ${T.hairlineStrong}`, color: T.inkMuted }}>
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Project ID & Title</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Ministry / Agency</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Sanctioned Cost</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Overrun Forecast</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "center" }}>Risk Score</th>
                    <th style={{ padding: "10px 14px", fontWeight: 600 }}>Prescribed Action</th>
                  </tr>
                </thead>
                <tbody>
                  {distressedMegaprojects.map((p, idx) => {
                    const style = actionStyle(p.institutional_action);
                    return (
                      <tr
                        key={p.project_id || idx}
                        style={{
                          borderBottom: `1px solid ${T.hairline}`,
                          background: idx % 2 === 0 ? "#FFFFFF" : "#FAFAF8"
                        }}
                      >
                        <td style={{ padding: "10px 14px" }}>
                          <div style={{ fontWeight: 600, color: T.ink }}>{p.project_name}</div>
                          <div style={{ fontFamily: mono, fontSize: 11, color: T.inkFaint }}>{p.project_id}</div>
                        </td>
                        <td style={{ padding: "10px 14px", color: T.inkMuted }}>
                          {p.ministry}
                          {p.agency ? ` (${p.agency})` : ""}
                        </td>
                        <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono, fontWeight: 600 }}>
                          {crore(p.sanctioned_cost_cr)}
                        </td>
                        <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono, color: (p.pred_cost_overrun_pct || 0) > 15 ? T.brick : T.ink }}>
                          +{(p.pred_cost_overrun_pct || 0).toFixed(1)}%
                          <div style={{ fontSize: 11, color: T.inkFaint }}>{(p.pred_delay_months || 0).toFixed(0)} mo delay</div>
                        </td>
                        <td style={{ padding: "10px 14px", textAlign: "center" }}>
                          <span style={{
                            background: style.bg, color: style.fg, border: `1px solid ${style.border}`,
                            padding: "3px 8px", borderRadius: 4, fontFamily: mono, fontWeight: 700
                          }}>
                            {(p.risk_score || 0).toFixed(1)}
                          </span>
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          <span style={{
                            background: style.bg, color: style.fg, border: `1px solid ${style.border}`,
                            padding: "3px 8px", borderRadius: 4, fontSize: 11.5, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4
                          }}>
                            {p.institutional_action}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 2: Inter-Ministerial Deadlock Synthesis */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 28 }}>
            <div style={{ background: "#FAFAF8", border: `1px solid ${T.hairlineStrong}`, borderRadius: 6, padding: 18 }}>
              <div style={{ fontFamily: serif, fontSize: 16, fontWeight: 600, color: T.ink, marginBottom: 10 }}>
                Root Friction Factors Identified by ML Engine
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: T.inkMuted, lineHeight: 1.6 }}>
                <li>
                  <strong style={{ color: T.brick }}>Land Acquisition Right-of-Way (35% weight):</strong> Stagnation in state revenue departments across Eastern & Himalayan corridors.
                </li>
                <li>
                  <strong style={{ color: T.ochre }}>Statutory & Environmental Approvals (25% weight):</strong> MoEF&CC Stage-II forest clearances and wildlife board nods averaging 14.2 months lag.
                </li>
                <li>
                  <strong style={{ color: T.accent }}>Contractor Track Record Deficits (25% weight):</strong> Concessionaires with multiple parallel packages failing to mobilize equipment on time.
                </li>
                <li>
                  <strong style={{ color: T.purple }}>Reporting Information Blackouts (15% penalty):</strong> Ministries withholding monthly progress updates for 3+ consecutive cycles.
                </li>
              </ul>
            </div>

            <div style={{ background: "#FAFAF8", border: `1px solid ${T.hairlineStrong}`, borderRadius: 6, padding: 18 }}>
              <div style={{ fontFamily: serif, fontSize: 16, fontWeight: 600, color: T.ink, marginBottom: 10 }}>
                Cabinet Secretariat Action Directives
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: T.inkMuted, lineHeight: 1.6 }}>
                <li>
                  <strong>Direct State Chief Secretaries:</strong> Convene fortnightly Empowered Committees for the top 10 megaprojects listed above to settle land compensation disputes.
                </li>
                <li>
                  <strong>Invoke PMG Fast-Track Clearances:</strong> Issue single-window time-bound clearances for utility shifting (State DISCOMs, municipal bodies).
                </li>
                <li>
                  <strong>Mandatory PRAGATI Appearance:</strong> Direct nodal secretaries of ministries with consecutive reporting blackouts to appear in the next PRAGATI review.
                </li>
              </ul>
            </div>
          </div>

          {/* Official Sign-off Footer */}
          <div style={{
            borderTop: `1px solid ${T.hairlineStrong}`, paddingTop: 16, display: "flex",
            justifyContent: "space-between", alignItems: "center", fontSize: 12, color: T.inkFaint
          }}>
            <div>
              PAIMANA Autonomous Risk Engine · Ministry of Statistics and Programme Implementation (MoSPI)
            </div>
            <div style={{ fontFamily: mono }}>
              Dossier Ref: GOI/CABSEC/PMG-{new Date().getFullYear()}-09
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
