import React, { useState, useMemo } from "react";
import { Compass, MapPin, AlertTriangle, ShieldAlert, CheckCircle2, ChevronRight, Layers, ArrowUpRight } from "lucide-react";
import { T, sans, serif, mono, crore, actionStyle } from "./tokens";

const CORRIDOR_DEFS = [
  {
    id: "North",
    name: "Northern Industrial & Himalayan Corridor",
    states: ["Uttar Pradesh", "Punjab", "Haryana", "Uttarakhand", "Himachal Pradesh", "Jammu and Kashmir", "Delhi"],
    bottlenecks: "Himalayan geotechnical clearances, environmental nods, and Delhi-NCR utility shifting.",
    strategicFocus: "Dedicated Freight Corridor (Eastern DFC), Delhi-Dehradun Expressway, Strategic Border Roads."
  },
  {
    id: "West",
    name: "Western Coastal & Economic Corridor",
    states: ["Maharashtra", "Gujarat", "Rajasthan", "Goa"],
    bottlenecks: "Coastal Regulation Zone (CRZ) approvals, urban right-of-way in MMR, and port connectivity clearances.",
    strategicFocus: "Mumbai-Ahmedabad High Speed Rail, Western DFC, JNPT Vadodara Expressway."
  },
  {
    id: "South",
    name: "Southern Industrial & Tech Corridor",
    states: ["Tamil Nadu", "Karnataka", "Telangana", "Andhra Pradesh", "Kerala"],
    bottlenecks: "Forest diversion clearances in Western Ghats and state-level land acquisition compensation litigation.",
    strategicFocus: "Bangalore-Chennai Expressway, Vizag Industrial Corridor, High-Speed Railway links."
  },
  {
    id: "East",
    name: "Eastern Mineral & Freight Corridor",
    states: ["West Bengal", "Odisha", "Bihar", "Jharkhand"],
    bottlenecks: "Coal block evacuation clearances, land acquisition resistance, and law & order in mineral belts.",
    strategicFocus: "Paradip/Dhamra port rail links, National Waterway-1, Coal India super-thermal evacuation."
  },
  {
    id: "Central",
    name: "Central Energy & Mining Belt",
    states: ["Madhya Pradesh", "Chhattisgarh"],
    bottlenecks: "Inter-state river linking clearances, dense forest diversions, and contractor equipment mobilization.",
    strategicFocus: "Singrauli Power Hub, Ken-Betwa river link, Bundelkhand Expressway expansion."
  },
  {
    id: "North-East",
    name: "North-Eastern Strategic Gateway",
    states: ["Assam", "Arunachal Pradesh", "Meghalaya", "Manipur", "Tripura", "Nagaland", "Mizoram", "Sikkim"],
    bottlenecks: "Monsoon flooding seasonality (limited 5-month working window), seismic fault zones, and border clearances.",
    strategicFocus: "Trans-Arunachal Highway, Sivok-Rangpo Railway Line, Kaladan Multi-Modal Transit."
  }
];

export default function CorridorGisView({ projects = [] }) {
  const [selectedCorridorId, setSelectedCorridorId] = useState("North");
  const [sectorFilter, setSectorFilter] = useState("all");

  // Sector list from actual data
  const sectors = useMemo(() => {
    const s = new Set();
    projects.forEach((p) => { if (p.sector) s.add(p.sector); });
    return ["all", ...Array.from(s).sort()];
  }, [projects]);

  // Aggregate corridor stats
  const corridorStats = useMemo(() => {
    return CORRIDOR_DEFS.map((c) => {
      const matched = projects.filter((p) => {
        const matchesRegion = p.region === c.id || (p.state && c.states.includes(p.state));
        const matchesSector = sectorFilter === "all" || p.sector === sectorFilter;
        return matchesRegion && matchesSector;
      });

      const totalCost = matched.reduce((acc, p) => acc + (p.sanctioned_cost_cr || 0), 0);
      const avgRisk = matched.length > 0 ? matched.reduce((acc, p) => acc + (p.risk_score || 0), 0) / matched.length : 0;
      const avgDelay = matched.length > 0 ? matched.reduce((acc, p) => acc + (p.pred_delay_months || 0), 0) / matched.length : 0;
      const highRiskCount = matched.filter((p) => (p.risk_score || 0) >= 45).length;

      return {
        ...c,
        matchedCount: matched.length,
        totalCost,
        avgRisk: Math.round(avgRisk * 10) / 10,
        avgDelay: Math.round(avgDelay * 10) / 10,
        highRiskCount,
        projects: matched.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
      };
    });
  }, [projects, sectorFilter]);

  const activeCorridor = corridorStats.find((c) => c.id === selectedCorridorId) || corridorStats[0];

  return (
    <main style={{ maxWidth: 1320, margin: "0 auto", padding: "28px 28px 60px", fontFamily: sans }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 14 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <Compass size={22} color={T.accent} />
            <div style={{ fontFamily: serif, fontSize: 24, fontWeight: 600, color: T.ink }}>
              National GIS Infrastructure Corridor Intelligence
            </div>
          </div>
          <div style={{ fontSize: 13, color: T.inkMuted }}>
            Spatial risk concentration across India's 6 National Economic Corridors. Identifies regional clear-of-way barriers, environmental bottlenecks, and state-level friction.
          </div>
        </div>

        {/* Sector Filter Chips */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, color: T.inkFaint, fontWeight: 500 }}>Sector:</span>
          {sectors.slice(0, 6).map((sec) => (
            <button
              key={sec}
              onClick={() => setSectorFilter(sec)}
              style={{
                padding: "5px 10px", borderRadius: 4, fontSize: 12, cursor: "pointer",
                border: `1px solid ${sectorFilter === sec ? T.accent : T.hairlineStrong}`,
                background: sectorFilter === sec ? T.accentBg : T.panel,
                color: sectorFilter === sec ? T.accent : T.ink,
                fontWeight: sectorFilter === sec ? 600 : 400,
                transition: "all 0.15s ease"
              }}
            >
              {sec === "all" ? "All Corridors" : sec}
            </button>
          ))}
        </div>
      </div>

      {/* 6 Corridor Cards Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16, marginBottom: 30 }}>
        {corridorStats.map((c) => {
          const isSelected = c.id === selectedCorridorId;
          const isCritical = c.avgRisk >= 40 || c.highRiskCount >= 10;
          const statusBg = isCritical ? T.brickBg : c.avgRisk >= 30 ? T.ochreBg : T.greenBg;
          const statusFg = isCritical ? T.brick : c.avgRisk >= 30 ? T.ochre : T.green;
          const statusBorder = isCritical ? T.brickBorder : c.avgRisk >= 30 ? T.ochreBorder : T.greenBorder;

          return (
            <div
              key={c.id}
              onClick={() => setSelectedCorridorId(c.id)}
              style={{
                background: T.panel,
                border: `2px solid ${isSelected ? T.accent : T.hairline}`,
                borderRadius: 8, padding: "18px 20px", cursor: "pointer",
                boxShadow: isSelected ? "0 4px 12px rgba(24, 69, 112, 0.12)" : "0 1px 3px rgba(0,0,0,0.03)",
                transition: "all 0.15s ease",
                position: "relative"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 11, color: T.accent, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.6 }}>
                    CORRIDOR {c.id}
                  </div>
                  <div style={{ fontFamily: serif, fontSize: 17, fontWeight: 600, color: T.ink, marginTop: 2 }}>
                    {c.name}
                  </div>
                </div>

                <span style={{
                  background: statusBg, color: statusFg, border: `1px solid ${statusBorder}`,
                  padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600, fontFamily: mono
                }}>
                  Risk {c.avgRisk.toFixed(1)}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, padding: "10px 0", borderTop: `1px solid ${T.hairline}`, borderBottom: `1px solid ${T.hairline}`, marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 11, color: T.inkFaint }}>PROJECTS</div>
                  <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 600, color: T.ink }}>{c.matchedCount}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: T.inkFaint }}>CAPITAL VALUE</div>
                  <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 600, color: T.ink }}>{crore(c.totalCost)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: T.inkFaint }}>AVG DELAY</div>
                  <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 600, color: c.avgDelay > 18 ? T.brick : T.ink }}>
                    {c.avgDelay.toFixed(0)} mo
                  </div>
                </div>
              </div>

              <div style={{ fontSize: 11.5, color: T.inkMuted, marginBottom: 8, lineHeight: 1.4 }}>
                <strong style={{ color: T.ink }}>Key Bottleneck:</strong> {c.bottlenecks}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11.5 }}>
                <span style={{ color: c.highRiskCount > 0 ? T.brick : T.green, fontWeight: 600 }}>
                  {c.highRiskCount} Critical Projects Flagged
                </span>
                <span style={{ color: T.accent, fontWeight: 600, display: "flex", alignItems: "center", gap: 2 }}>
                  {isSelected ? "Active Focus" : "Inspect Corridor"} <ChevronRight size={13} />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Corridor Drill-Down Table */}
      <div style={{ background: T.panel, border: `1px solid ${T.hairline}`, borderRadius: 8, padding: 22, boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <div>
            <div style={{ fontFamily: serif, fontSize: 19, fontWeight: 600, color: T.ink }}>
              Corridor Focus: {activeCorridor.name} ({activeCorridor.matchedCount} Projects)
            </div>
            <div style={{ fontSize: 12.5, color: T.inkMuted, marginTop: 2 }}>
              Priority infrastructure assets mapped within {activeCorridor.states.join(", ")}
            </div>
          </div>
          <div style={{ fontSize: 12, color: T.inkFaint }}>
            Strategic Corridor Objective: <strong style={{ color: T.ink }}>{activeCorridor.strategicFocus}</strong>
          </div>
        </div>

        {activeCorridor.projects.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: T.inkFaint }}>
            No projects found in this corridor matching the current sector filter.
          </div>
        ) : (
          <div style={{ border: `1px solid ${T.hairlineStrong}`, borderRadius: 6, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
              <thead>
                <tr style={{ background: "#F6F8FA", borderBottom: `1px solid ${T.hairlineStrong}`, color: T.inkMuted }}>
                  <th style={{ padding: "10px 14px", fontWeight: 600 }}>Project ID & Title</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600 }}>Ministry / Sector</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Sanctioned Cost</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Progress</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "right" }}>Delay Forecast</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600, textAlign: "center" }}>Risk Score</th>
                  <th style={{ padding: "10px 14px", fontWeight: 600 }}>Institutional Action</th>
                </tr>
              </thead>
              <tbody>
                {activeCorridor.projects.slice(0, 15).map((p, idx) => {
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
                        <div style={{ fontSize: 11, color: T.inkFaint }}>{p.sector}</div>
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono, fontWeight: 600 }}>
                        {crore(p.sanctioned_cost_cr)}
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono }}>
                        {(p.physical_progress_pct || 0).toFixed(0)}%
                        <div style={{ fontSize: 11, color: T.inkFaint }}>Fin: {(p.financial_progress_pct || 0).toFixed(0)}%</div>
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "right", fontFamily: mono, color: (p.pred_delay_months || 0) > 18 ? T.brick : T.ink }}>
                        {(p.pred_delay_months || 0).toFixed(0)} mo
                        <div style={{ fontSize: 11, color: T.inkFaint }}>Prob: {((p.pred_delay_probability || 0) * 100).toFixed(0)}%</div>
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
        )}
      </div>
    </main>
  );
}
