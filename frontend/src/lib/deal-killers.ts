const SEVERITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2, info: 3 }

const DECISION_IMPACT = [
  'master_plan_required',
  'no_street_access',
  'public_ownership',
  'tax_delinquent',
  'sheriff_sale',
  'flood_zone',
  'historic_district',
]

export const DEAL_KILLER_LIMIT = 3

export interface DealKiller {
  code: string
  label: string
  severity: string
}

function impactRank(code: string): number {
  const index = DECISION_IMPACT.indexOf(code)
  return index === -1 ? DECISION_IMPACT.length : index
}

export function rankedDealKillers(flags: unknown[]): DealKiller[] {
  const parsed = flags
    .filter((flag): flag is Record<string, unknown> => typeof flag === 'object' && flag !== null)
    .map((flag) => ({
      code: String(flag.code ?? ''),
      label: String(flag.label ?? flag.code ?? ''),
      severity: String(flag.severity ?? 'info'),
    }))
    .filter((flag) => flag.severity !== 'info')

  return parsed
    .sort(
      (a, b) =>
        (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9) ||
        impactRank(a.code) - impactRank(b.code) ||
        a.code.localeCompare(b.code),
    )
    .slice(0, DEAL_KILLER_LIMIT)
}
