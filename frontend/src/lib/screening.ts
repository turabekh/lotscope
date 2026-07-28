import type { Recommendation } from '@/lib/types'

export interface ScreeningDisplay {
  label: string
  tone: string
  icon: string
}

const DISPLAY: Record<Recommendation, ScreeningDisplay> = {
  strong_candidate: { label: 'Strong candidate', tone: 'positive', icon: 'trending_up' },
  worth_investigating: { label: 'Worth investigating', tone: 'primary', icon: 'search' },
  high_entitlement_risk: { label: 'High entitlement risk', tone: 'warning', icon: 'gavel' },
  economics_unattractive: {
    label: 'Economics unattractive',
    tone: 'warning',
    icon: 'trending_down',
  },
  insufficient_data: { label: 'Insufficient data', tone: 'grey-6', icon: 'help_outline' },
  likely_pass: { label: 'Likely pass', tone: 'grey-7', icon: 'do_not_disturb_on' },
}

export function screeningDisplay(recommendation: Recommendation | null): ScreeningDisplay | null {
  return recommendation === null ? null : DISPLAY[recommendation]
}
