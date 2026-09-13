import { AlertTriangle, ShieldAlert, FileWarning, CheckCircle2 } from "lucide-react";

export const T = {
  paper: "#F7F6F2",
  panel: "#FFFFFF",
  panelMuted: "#FAFAF8",
  ink: "#12203A",
  inkMuted: "#505A69",
  inkFaint: "#7E8896",
  hairline: "#E1E4DC",
  hairlineStrong: "#C8CCC0",
  brick: "#8B1E1E",
  brickBg: "#FDF0EF",
  brickBorder: "#E8C8C6",
  ochre: "#8A5A00",
  ochreBg: "#FEF7E9",
  ochreBorder: "#EBDBB2",
  green: "#245838",
  greenBg: "#EBF3EC",
  greenBorder: "#C0D8C6",
  confidence: "#2B5278",
  confidenceBg: "#EDF3F8",
  confidenceFaint: "#A5B8CC",
  accent: "#184570",
  accentBg: "#EBF2F9",
  accentBorder: "#BCD0E4",
  purple: "#5B2E91",
  purpleBg: "#F5F0FB",
  purpleBorder: "#DAC9F1",
};

export const serif = "'Source Serif 4', Georgia, serif";
export const sans = "'IBM Plex Sans', system-ui, -apple-system, sans-serif";
export const mono = "'IBM Plex Mono', ui-monospace, monospace";

export function actionStyle(action) {
  switch (action) {
    case "PRAGATI candidate":
      return { fg: T.brick, bg: T.brickBg, border: T.brickBorder, icon: AlertTriangle };
    case "Escalate to PMG":
      return { fg: T.brick, bg: T.brickBg, border: T.brickBorder, icon: ShieldAlert };
    case "Flag to line ministry":
      return { fg: T.ochre, bg: T.ochreBg, border: T.ochreBorder, icon: FileWarning };
    default:
      return { fg: T.green, bg: T.greenBg, border: T.greenBorder, icon: CheckCircle2 };
  }
}

export function crore(n) {
  return `\u20B9${Math.round(n || 0).toLocaleString("en-IN")} cr`;
}

export function clip01(x, lo, hi) {
  if (hi <= lo) return 0;
  return Math.max(0, Math.min(1, (x - lo) / (hi - lo)));
}

export function computeRiskConfidence(row, norm) {
  norm = norm || { cost_overrun_p99: 22.0, delay_severity_p99: 68.9, approval_delay_p99: 21.8 };
  const costComponent = clip01(Math.max(0, row.pred_cost_overrun_pct || 0), 0, norm.cost_overrun_p99);
  const delaySeverity = (row.pred_delay_probability || 0) * Math.max(0, row.pred_delay_months || 0);
  const delayComponent = clip01(delaySeverity, 0, norm.delay_severity_p99);
  const landPenaltyMap = { not_started: 1.0, partial: 0.5, complete: 0.0 };
  const landPenalty = landPenaltyMap[row.land_acquisition_status] ?? 0.3;
  const approvalComponent = clip01(row.approval_delay_months || 0, 0, norm.approval_delay_p99);
  const contractorComponent = 1 - (row.contractor_track_record_score ?? 0.5);
  const financingComponent = row.financing_irregularity_flag ? 1 : 0;
  const structuralComponent =
    0.35 * landPenalty + 0.25 * approvalComponent + 0.25 * contractorComponent + 0.15 * financingComponent;
  let riskScore = 100 * (0.4 * costComponent + 0.35 * delayComponent + 0.25 * structuralComponent);
  if ((row.consecutive_missed_cycles || 0) >= 3) riskScore += 8;
  riskScore = Math.round(Math.max(0, Math.min(100, riskScore)) * 10) / 10;

  const monthsStale = Math.max(0, Math.min(Number(row.months_since_last_report || 0), 12));
  const freshness = Math.exp(-monthsStale / 3.5);
  const completeness = Math.max(0, Math.min(1, Number(row.evidence_completeness_score ?? 0.75)));
  const pDelay = Math.max(0, Math.min(1, Number(row.pred_delay_probability ?? 0.5)));
  const modelCertainty = Math.abs(2 * pDelay - 1);
  const physical = Number(row.physical_progress_pct || 0);
  const financial = Number(row.financial_progress_pct || 0);
  const gap = Math.min(Math.abs(financial - physical) / 100, 1);
  const orig = Math.max(Number(row.sanctioned_cost_cr || 0), 0);
  const revised = Math.max(Number(row.revised_cost_cr ?? orig), 0);
  const expenditure = Math.max(Number(row.cumulative_expenditure_cr || 0), 0);
  const spendRatio = Math.max(0, Math.min(1.5, expenditure / Math.max(revised || orig, 1)));
  const spendGap = Math.min(Math.abs(spendRatio * 100 - financial) / 100, 1);
  const consistency = Math.max(0, Math.min(1, 1 - (0.65 * gap + 0.35 * spendGap)));
  const costSignal = 1 - Math.exp(-Math.max(0, Number(row.pred_cost_overrun_pct || 0)) / 30);
  const delaySignal = 1 - Math.exp(-Math.max(0, Number(row.pred_delay_months || 0)) / 36);
  const meanSignal = (pDelay + costSignal + delaySignal) / 3;
  const predictionConcordance = Math.max(0, Math.min(1, 1 - Math.sqrt(
    ((pDelay - meanSignal) ** 2 + (costSignal - meanSignal) ** 2 + (delaySignal - meanSignal) ** 2) / 3
  ) * 1.8));
  const confidenceScore = Math.round(Math.max(8, Math.min(98,
    100 * (0.35 * completeness + 0.15 * freshness + 0.20 * modelCertainty + 0.15 * consistency + 0.15 * predictionConcordance) ** 3
  )) * 10) / 10;

  const stuckStructural = row.land_acquisition_status === "not_started" && (row.consecutive_missed_cycles || 0) >= 3;
  let action;
  if (stuckStructural && riskScore >= 18) action = "PRAGATI candidate";
  else if ((row.sanctioned_cost_cr || 0) >= 500 && riskScore >= 45) action = "Escalate to PMG";
  else if (riskScore >= 30) action = "Flag to line ministry";
  else action = "Routine monitoring";
  return { risk_score: riskScore, confidence_score: confidenceScore, institutional_action: action };
}
