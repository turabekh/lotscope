import type { ParcelChecklist, VerdictResult } from '@/lib/types'

export const BY_RIGHT_QUALIFIER =
  'Appears dimensionally eligible under the listed base-district standards. This is a preliminary screening, not a construction approval.'

export const BY_RIGHT_NOT_MET =
  'The listed base-district standards are not met, so a variance or special exception would be needed.'

const UNEVALUATED_FALLBACK = 'overlays, access, utilities, and title'

export function outstandingCheckLabels(checklist: ParcelChecklist | null): string[] {
  if (!checklist) return []
  const labels = checklist.items
    .filter((item) => item.status === 'not_evaluated')
    .map((item) => item.category.trim())
    .filter((category) => category.length > 0)
  return [...new Set(labels)]
}

export function byRightQualifier(checklist: ParcelChecklist | null): string {
  const outstanding = outstandingCheckLabels(checklist)
  const subject = outstanding.length > 0 ? outstanding.join(', ') : UNEVALUATED_FALLBACK
  return `${BY_RIGHT_QUALIFIER} Still to check: ${subject}.`
}

export function baseDistrictSummary(verdict: VerdictResult): string {
  if (verdict.by_right_units !== null && verdict.by_right_units > 0) {
    const plural = verdict.by_right_units === 1 ? '' : 's'
    return `Base district permits ${verdict.by_right_units} unit${plural}`
  }
  return 'Base district standards met'
}
