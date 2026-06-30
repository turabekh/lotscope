const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

const numberFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '—'
  return currencyFormatter.format(value)
}

export function formatRange(
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  if (low == null || high == null) return '—'
  return `${formatCurrency(low)} – ${formatCurrency(high)}`
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '—'
  return numberFormatter.format(value)
}

export function formatSqft(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${numberFormatter.format(value)} sq ft`
}

export function formatFeet(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${numberFormatter.format(value)} ft`
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${Math.round(value * 100)}%`
}

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return 'grey'
  if (score >= 65) return 'positive'
  if (score >= 45) return 'amber-8'
  return 'negative'
}

export function scoreLabel(score: number | null | undefined): string {
  if (score == null) return 'No score'
  if (score >= 65) return 'Opportunity'
  if (score >= 45) return 'Mixed'
  return 'Caution'
}

export function scoreVar(score: number | null | undefined): string {
  if (score == null) return 'var(--lot-score-none)'
  if (score >= 65) return 'var(--lot-score-positive)'
  if (score >= 45) return 'var(--lot-score-mixed)'
  return 'var(--lot-score-caution)'
}

const SEVERITY_VAR: Record<string, string> = {
  high: 'var(--lot-sev-high)',
  medium: 'var(--lot-sev-medium)',
  low: 'var(--lot-sev-low)',
  info: 'var(--lot-sev-info)',
}

export function severityVar(severity: string): string {
  return SEVERITY_VAR[severity] ?? 'var(--lot-sev-low)'
}

const SEVERITY_COLOR: Record<string, string> = {
  high: 'negative',
  medium: 'warning',
  low: 'grey-7',
  info: 'info',
}

export function severityColor(severity: string): string {
  return SEVERITY_COLOR[severity] ?? 'grey-7'
}

const SEVERITY_ICON: Record<string, string> = {
  high: 'error',
  medium: 'warning',
  low: 'info',
  info: 'info',
}

export function severityIcon(severity: string): string {
  return SEVERITY_ICON[severity] ?? 'info'
}
