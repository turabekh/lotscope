import type { BuildabilityPosture, ParcelChecklist, VerdictResult } from '@/lib/types'

export const BY_RIGHT_QUALIFIER =
  'Appears dimensionally eligible under the listed base-district standards. This is a preliminary screening, not a construction approval.'

export const BY_RIGHT_NOT_MET =
  'The listed base-district standards are not met, so a variance or special exception would be needed.'

export const MASTER_PLAN_REQUIRED =
  'Development is not permitted by right in this district: an approved master plan or equivalent review is required.'

export const BUILDABILITY_UNDETERMINED =
  'Base-district standards could not be evaluated for this parcel.'

const UNEVALUATED_FALLBACK = 'overlays, access, utilities, and title'

export interface PostureDisplay {
  label: string
  icon: string
  color: string
  tone: 'positive' | 'warning' | 'neutral' | 'caution'
  qualifier: string
}

const POSTURE_DISPLAY: Record<BuildabilityPosture, PostureDisplay> = {
  by_right: {
    label: 'Dimensionally eligible',
    icon: 'check_circle',
    color: 'positive',
    tone: 'positive',
    qualifier: BY_RIGHT_QUALIFIER,
  },
  variance_required: {
    label: 'Variance likely',
    icon: 'gavel',
    color: 'warning',
    tone: 'warning',
    qualifier: BY_RIGHT_NOT_MET,
  },
  master_plan_required: {
    label: 'Master plan required',
    icon: 'account_balance',
    color: 'blue-grey-6',
    tone: 'caution',
    qualifier: MASTER_PLAN_REQUIRED,
  },
  undetermined: {
    label: 'Buildability uncertain',
    icon: 'help_outline',
    color: 'grey-6',
    tone: 'neutral',
    qualifier: BUILDABILITY_UNDETERMINED,
  },
}

const UNIT_LABELS: Record<BuildabilityPosture, string> = {
  by_right: 'By-right units',
  variance_required: 'Units if a variance is granted',
  master_plan_required: 'By-right units',
  undetermined: 'Units the standards would support',
}

const UNIT_NOTES: Record<BuildabilityPosture, string> = {
  by_right:
    'Dwelling units the base-district standards appear to allow without a variance. Subject to overlays, access, parking, utilities, title, and the checks below.',
  variance_required:
    'This lot does not meet the district minimums, so these units are not available by right. This is what the standards would support if a variance or special exception were granted.',
  master_plan_required:
    'No units are available by right in this district. Density is set through the master-plan approval, not by the base-district standards.',
  undetermined:
    'Conformance with the district minimums could not be determined, so it is unknown whether these units are available by right or would need a variance.',
}

const MASTER_PLAN_UNIT_VALUE = 'None'

export function postureFromSummary(summary: string | null | undefined): BuildabilityPosture | null {
  return summary?.toLowerCase().includes('master plan') ? 'master_plan_required' : null
}

export function resolvePosture(
  verdict: VerdictResult,
  checklist: ParcelChecklist | null | undefined,
): BuildabilityPosture {
  if (checklist?.posture) return checklist.posture
  const fromSummary = postureFromSummary(verdict.summary)
  if (fromSummary) return fromSummary
  if (verdict.can_build_by_right) return 'by_right'
  if (verdict.needs_variance) return 'variance_required'
  return 'undetermined'
}

export function postureDisplay(posture: BuildabilityPosture): PostureDisplay {
  return POSTURE_DISPLAY[posture]
}

export function unitCountLabel(posture: BuildabilityPosture): string {
  return UNIT_LABELS[posture]
}

export function unitCountNote(posture: BuildabilityPosture): string {
  return UNIT_NOTES[posture]
}

export function unitCountValue(posture: BuildabilityPosture, units: number | null): string {
  if (posture === 'master_plan_required') return MASTER_PLAN_UNIT_VALUE
  return units === null ? '—' : String(units)
}

export function outstandingCheckLabels(checklist: ParcelChecklist | null): string[] {
  if (!checklist) return []
  const labels = checklist.items
    .filter((item) => item.status === 'not_evaluated')
    .map((item) => item.label.trim())
    .filter((label) => label.length > 0)
  return [...new Set(labels)]
}

export function flaggedCheckLabels(checklist: ParcelChecklist | null): string[] {
  if (!checklist) return []
  const labels = checklist.items
    .filter((item) => item.status === 'fail' || item.status === 'potential_issue')
    .map((item) => item.label.trim())
    .filter((label) => label.length > 0)
  return [...new Set(labels)]
}

export function byRightQualifier(checklist: ParcelChecklist | null): string {
  const flagged = flaggedCheckLabels(checklist)
  const outstanding = outstandingCheckLabels(checklist)
  const subject = outstanding.length > 0 ? outstanding.join(', ') : UNEVALUATED_FALLBACK
  const flaggedClause =
    flagged.length > 0
      ? ` Flagged for a closer look: ${flagged.join(', ')} — this eligibility may not hold.`
      : ''
  return `${BY_RIGHT_QUALIFIER}${flaggedClause} Still to check: ${subject}.`
}

export function buildQualifier(
  posture: BuildabilityPosture,
  checklist: ParcelChecklist | null,
): string {
  return posture === 'by_right' ? byRightQualifier(checklist) : POSTURE_DISPLAY[posture].qualifier
}

export function baseDistrictSummary(verdict: VerdictResult): string {
  if (verdict.by_right_units !== null && verdict.by_right_units > 0) {
    const plural = verdict.by_right_units === 1 ? '' : 's'
    return `Base district permits ${verdict.by_right_units} unit${plural}`
  }
  return 'Base district standards met'
}
