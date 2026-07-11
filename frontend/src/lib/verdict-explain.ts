import type { VerdictResult } from '@/lib/types'

export const BUILDABILITY_WEIGHT = 0.6
export const RISK_WEIGHT = 0.4

export const SEVERITY_WEIGHT: Record<string, number> = {
  high: 40,
  medium: 20,
  low: 10,
  info: 0,
}

export function flagWeight(severity: string): number {
  return SEVERITY_WEIGHT[severity] ?? 0
}

const SOURCE_LABELS: Record<string, string> = {
  li_event: 'L&I (Licenses & Inspections)',
  tax_status: 'Dept. of Revenue tax records',
  flood_zone: 'FEMA flood maps',
  historicdistricts_local: 'Philadelphia historic districts',
  zoning_overlays: 'Zoning overlays',
  zoning_rco: 'Registered community orgs',
  street_centerline: 'City street centerlines',
  zoning_standard: 'Zoning code standards',
  parcel: 'OPA / city parcel records',
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

const SEVERITY_HINT: Record<string, string> = {
  high: 'High severity — a likely deal-killer; verify before proceeding.',
  medium: 'Medium severity — material; factor it into price and plan.',
  low: 'Low severity — worth noting, usually manageable.',
  info: 'Informational — context, not necessarily a problem.',
}

export function severityHint(severity: string): string {
  return SEVERITY_HINT[severity] ?? ''
}

export interface ScoreBreakdown {
  buildability: number | null
  risk: number | null
  buildabilityTerm: number
  riskInverse: number
  riskTerm: number
  total: number
}

function clamp(value: number): number {
  return Math.max(0, Math.min(100, value))
}

export function scoreBreakdown(verdict: VerdictResult): ScoreBreakdown {
  const buildability = verdict.buildability_score
  const risk = verdict.risk_score
  const buildabilityTerm = BUILDABILITY_WEIGHT * (buildability ?? 0)
  const riskInverse = 100 - (risk ?? 0)
  const riskTerm = RISK_WEIGHT * riskInverse
  return {
    buildability,
    risk,
    buildabilityTerm: Math.round(buildabilityTerm * 10) / 10,
    riskInverse,
    riskTerm: Math.round(riskTerm * 10) / 10,
    total: Math.round(clamp(buildabilityTerm + riskTerm) * 10) / 10,
  }
}
