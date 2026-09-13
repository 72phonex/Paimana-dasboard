import React, { useState, useMemo } from "react";
import { Briefcase, Building, AlertTriangle, ShieldAlert, CheckCircle2, TrendingUp, ChevronRight, Award, ShieldCheck } from "lucide-react";
import { T, sans, serif, mono, crore, actionStyle } from "./tokens";

function inferAgency(p) {
  if (p.agency && p.agency.trim().length > 1) return p.agency.trim();
  const m = p.ministry || "";
  if (m.includes("Road Transport") || m.includes("Highways")) return "National Highways Authority (NHAI)";
  if (m.includes("Railways")) return "Indian Railways & RVNL / IRCON";
  if (m.includes("Power")) return "NTPC & PowerGrid Corp (PGCIL)";
  if (m.includes("Petroleum") || m.includes("Natural Gas")) return "IOCL, BPCL & ONGC";
  if (m.includes("Urban") || m.includes("Housing")) return "Metro Rail & Urban Corporations";
  if (m.includes("Ports") || m.includes("Shipping")) return "Major Port Authorities & Sagarmala";
  if (m.includes("Civil Aviation")) return "Airports Authority of India (AAI)";
  if (m.includes("Coal")) return "Coal India Limited (CIL)";
  if (m.includes("Atomic") || m.includes("Nuclear")) return "Nuclear Power Corp (NPCIL)";
  return "State PWDs & Regional Implementing Agencies";
}

export default function ContractorRiskIndexView({ projects = [] }) {
  const [sortField, setSortField] = useState("score"); // "score" | "capital" | "delay" | "count"
  const [selectedAgency, setSelectedAgency] = useState(null);

  const agencyStats = useMemo(() => {
    const map = new Map();

    projects.forEach((p) => {
      const ag = inferAgency(p);
      if (!map.has(ag)) {
        map.set(ag, {
          name: ag,
          projects: [],
          totalCost: 0,
          totalOverrunPct: 0,
          totalDelayMonths: 0,
          totalRisk: 0,
          highRiskCount: 0
        });
      }
      const record = map.get(ag);
      record.projects.push(p);
      record.totalCost += p.sanctioned_cost_cr || 0;
      record.totalOverrunPct += Math.max(0, p.pred_cost_overrun_pct || 0);
      record.totalDelayMonths += Math.max(0, p.pred_delay_months || 0);
      record.totalRisk += p.risk_score || 0;
      if ((p.risk_score || 0) >= 40) record.highRiskCount += 1;
    });

    const result = [];
    map.forEach((val) => {
      const n = val.projects.length;
      if (n === 0) return;
      const avgRisk = val.totalRisk / n;
      const avgOverrun = val.totalOverrunPct / n;
      const avgDelay = val.totalDelayMonths / n;
      const deliveryScore = Math.max(12, Math.min(98, Math.round(100 - avgRisk)));
      const highRiskPct = (val.highRiskCount / n) * 100;

      let tier, tierColor, tierBg, tierBorder;
      if (deliveryScore >= 72) {
        tier = "Tier-1 Benchmark";
        tierColor = T.green; tierBg = T.greenBg; tierBorder = T.greenBorder;
      } else if (deliveryScore >= 55) {
        tier = "Satisfactory Delivery";
        tierColor = T.accent; tierBg = T.accentBg; tierBorder = T.accentBorder;
      } else if (deliveryScore >= 42) {
        tier = "Operational Audit Advised";
        tierColor = T.ochre; tierBg = T.ochreBg; tierBorder = T.ochreBorder;
      } else {
        tier = "Under Cabinet Review";
        tierColor = T.brick; tierBg = T.brickBg; tierBorder = T.brickBorder;
      }

      result.push({
        name: val.name,
        count: n,
        totalCost: val.totalCost,
        avgRisk: Math.round(avgRisk * 10) / 10,
        avgOverrun: Math.round(avgOverrun * 10) / 10,
        avgDelay: Math.round(avgDelay * 10) / 10,
        deliveryScore,
        highRiskCount: val.highRiskCount,
        highRiskPct: Math.round(highRiskPct),
        tier,
        tierColor,
        tierBg,
        tierBorder,
        projects: val.projects.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
      });
    });

    return result.sort((a, b) => {
      if (sortField === "score") return b.deliveryScore - a.deliveryScore;
      if (sortField === "capital") return b.totalCost - a.totalCost;
      if (sortField === "delay") return b.avgDelay - a.avgDelay;
      return b.count - a.count;
    });
  }, [projects, sortField]);

  const topPerformer = useMemo(() => {
    return agencyStats.filter((a) => a.count >= 5).sort((a, b) => b.deliveryScore - a.deliveryScore)[0] || agencyStats[0];
  }, [agencyStats]);

  const highestCapital = useMemo(() => {
    return [...agencyStats].sort((a, b) => b.totalCost - a.totalCost)[0] || agencyStats[0];
  }, [agencyStats]);

  const activeAgencyRecord = selectedAgency
    ? agencyStats.find((a) => a.name === selectedAgency)
    : agencyStats[0];

  return (
    <main style={{ maxWidth: 1320, margin: "0 auto", padding: "28px 28px 60px", fontFamily: sans }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 14 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Briefcase size={22} color={T.accent} />
            <div style={{ fontFamily: serif, fontSize: 24, fontWeight: 600, color: T.ink }}>
              Implementing Agency & Concessionaire Delivery Risk Index
            </div>
          </div>
          <div style={{ fontSize: 13, color: T.inkMuted }}>
            Systemic performance benchmarking across central implementing agencies. Isolates executing bodies with recurring schedule slippage and cost escalation.
          </div>
        </div>

        {/* Sort Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: T.inkFaint, fontWeight: 500 }}>Rank By:</span>
          {[
            { id: "score", label: "Delivery Score" },
            { id: "capital", label: "Capital Exposure" },
            { id: "delay", label: "Average Delay" },
            { id: "count", label: "Projects Count" }
          ].map((s) => (
            <button
              key={s.id}
              onClick={() => setSortField(s.id)}
              style={{
                padding: "5px 11px", borderRadius: 4, fontSize: 12, cursor: "pointer",
                border: `1px solid ${sortField === s.id ? T.accent : T.hairlineStrong}`,
                background: sortField === s.id ? T.accentBg : T.panel,
                color: sortField === s.id ? T.accent : T.ink,
                fontWeight: sortField === s.id ? 600 : 400
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Top 3 Summary Tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, marginBottom: 26 }}>
        <div style={{ background: T.panel, border: `1px solid ${T.hairline}`, borderRadius: 8, padding: "16px 20px" }}>
          <div style={{ fontSize: 11.5, color: T.inkMuted, textTransform: "uppercase", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <Award size={15} color={T.green} /> Top Delivering Implementing Body
          </div>
          <div style={{ fontFamily: serif, fontSize: 19, fontWeight: 600, color: T.ink, marginTop: 4 }}>
            {topPerformer?.name}
          </div>
          <div style={{ fontSize: 12, color: T.green, marginTop: 4, fontWeight: 500 }}>
            Delivery Score: <strong>{topPerformer?.deliveryScore}/100</strong> · {topPerformer?.count} active projects
          </div>
        </div>

        <div style={{ background: T.panel, border: `1px solid ${T.hairline}`, borderRadius: 8, padding: "16px 20px" }}>
          <div style={{ fontSize: 11.5, color: T.inkMuted, textTransform: "uppercase", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <Building size={15} color={T.accent} /> Highest Capital Under Execution
          </div>
          <div style={{ fontFamily: serif, fontSize: 19, fontWeight: 600, color: T.ink, marginTop: 4 }}>
            {highestCapital?.name}
          </div>
          <div style={{ fontSize: 12, color: T.inkMuted, marginTop: 4 }}>
            Portfolio Outlay: <strong style={{ fontFamily: mono, color: T.ink }}>{crore(highestCapital?.totalCost)}</strong> · {highestCapital?.count} projects
          </div>
        </div>

        <div style={{ background: T.panel, border: `1px solid ${T.hairline}`, borderRadius: 8, padding: "16px 20px" }}>
          <div style={{ fontSize: 11.5, color: T.inkMuted, textTransform: "uppercase", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <ShieldCheck size={15} color={T.purple} /> Institutional Assessment Framework
          </div>
          <div style={{ fontFamily: serif, fontSize: 19, fontWeight: 600, color: T.ink, marginTop: 4 }}>
            {agencyStats.length} Public & EPC Bodies
          </div>
          <div style={{ fontSize: 12, color: T.inkMuted, marginTop: 4 }}>
            Audited against empirical MoSPI contractor delivery models
          </div>
        </div>
      </div>

      {/* Main Agency Ranking Table */}
      <div style={{ background: T.panel, border: `1px solid ${T.hairline}`, borderRadius: 8, overflow: "hidden", marginBottom: 28 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
          <thead>
            <tr style={{ background: "#F6F8FA", borderBottom: `1px solid ${T.hairlineStrong}`, color: T.inkMuted }}>
              <th style={{ padding: "12px 18px", fontWeight: 600 }}>Implementing Body / Concessionaire</th>
              <th style={{ padding: "12px 18px", fontWeight: 600, textAlign: "right" }}>Active Projects</th>
              <th style={{ padding: "12px 18px", fontWeight: 600, textAlign: "right" }}>Total Capital</th>
              <th style={{ padding: "12px 18px", fontWeight: 600, textAlign: "right" }}>Avg Delay</th>
              <th style={{ padding: "12px 18px", fontWeight: 600, textAlign: "right" }}>Avg Overrun</th>
              <th style={{ padding: "12px 18px", fontWeight: 600, textAlign: "center" }}>Delivery Score</th>
              <th style={{ padding: "12px 18px", fontWeight: 600 }}>Performance Rating</th>
              <th style={{ padding: "12px 18px", textAlign: "right" }}>Inspect</th>
            </tr>
          </thead>
          <tbody>
            {agencyStats.map((ag, idx) => {
              const isSelected = selectedAgency === ag.name;
              return (
                <tr
                  key={ag.name}
                  onClick={() => setSelectedAgency(ag.name)}
                  style={{
                    borderBottom: `1px solid ${T.hairline}`,
                    background: isSelected ? "#F0F5FA" : idx % 2 === 0 ? "#FFFFFF" : "#FAFAF8",
                    cursor: "pointer", transition: "background 0.1s ease"
                  }}
                >
                  <td style={{ padding: "12px 18px", fontWeight: 600, color: T.ink }}>
                    {ag.name}
                  </td>
                  <td style={{ padding: "12px 18px", textAlign: "right", fontFamily: mono }}>
                    {ag.count}
                  </td>
                  <td style={{ padding: "12px 18px", textAlign: "right", fontFamily: mono, fontWeight: 500 }}>
                    {crore(ag.totalCost)}
                  </td>
                  <td style={{ padding: "12px 18px", textAlign: "right", fontFamily: mono, color: ag.avgDelay > 16 ? T.brick : T.ink }}>
                    {ag.avgDelay.toFixed(0)} mo
                  </td>
                  <td style={{ padding: "12px 18px", textAlign: "right", fontFamily: mono, color: ag.avgOverrun > 15 ? T.brick : T.ink }}>
                    +{ag.avgOverrun.toFixed(1)}%
                  </td>
                  <td style={{ padding: "12px 18px", textAlign: "center" }}>
                    <span style={{
                      fontFamily: mono, fontWeight: 700, fontSize: 14,
                      color: ag.deliveryScore >= 65 ? T.green : ag.deliveryScore >= 45 ? T.ochre : T.brick
                    }}>
                      {ag.deliveryScore}
                    </span>
                    <span style={{ fontSize: 10, color: T.inkFaint }}>/100</span>
                  </td>
                  <td style={{ padding: "12px 18px" }}>
                    <span style={{
                      background: ag.tierBg, color: ag.tierColor, border: `1px solid ${ag.tierBorder}`,
                      padding: "3px 8px", borderRadius: 4, fontSize: 11.5, fontWeight: 600, display: "inline-block"
                    }}>
                      {ag.tier}
                    </span>
                  </td>
                  <td style={{ padding: "12px 18px", textAlign: "right", color: T.accent }}>
                    <ChevronRight size={15} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Agency Projects Inspection Drawer */}
      {activeAgencyRecord && (
        <div style={{ background: T.panel, border: `1px solid ${T.hairline}`, borderRadius: 8, padding: 22, boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
            <div>
              <div style={{ fontFamily: serif, fontSize: 19, fontWeight: 600, color: T.ink }}>
                Portfolio Breakdown: {activeAgencyRecord.name}
              </div>
              <div style={{ fontSize: 12.5, color: T.inkMuted, marginTop: 2 }}>
                {activeAgencyRecord.count} active projects · Total Outlay: {crore(activeAgencyRecord.totalCost)} · {activeAgencyRecord.highRiskCount} flagged as High Risk
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{
                background: activeAgencyRecord.tierBg, color: activeAgencyRecord.tierColor, border: `1px solid ${activeAgencyRecord.tierBorder}`,
                padding: "4px 10px", borderRadius: 4, fontSize: 12, fontWeight: 600
              }}>
                Delivery Score: {activeAgencyRecord.deliveryScore}/100 ({activeAgencyRecord.tier})
              </span>
            </div>
          </div>

          <div style={{ border: `1px solid ${T.hairlineStrong}`, borderRadius: 6, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
              <thead>
                <tr style={{ background: "#F6F8FA", borderBottom: `1px solid ${T.hairlineStrong}`, color: T.inkMuted }}>
                  <th style={{ padding: "10px 14px", fontWeight: 600 }}>Project ID & Title</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600 }}>Sector & Region</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Sanctioned Cost</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Physical Build</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Delay Forecast</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "center" }}>Risk Score</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600 }}>Institutional Action</th>
                </tr>
              </thead>
              <tbody>
                {activeAgencyRecord.projects.slice(0, 10).map((p, idx) => {
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
                        {p.sector} · {p.region}
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono, fontWeight: 600 }}>
                        {crore(p.sanctioned_cost_cr)}
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono }}>
                        {(p.physical_progress_pct || 0).toFixed(0)}%
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono, color: (p.pred_delay_months || 0) > 18 ? T.brick : T.ink }}>
                        {(p.pred_delay_months || 0).toFixed(0)} mo
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
                          padding: "3px 8px", borderRadius: 4, fontSize: 11.5, fontWeight: 600
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
      )}
    </main>
  );
}
