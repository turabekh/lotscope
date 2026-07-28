import { describe, expect, it } from 'vitest'

import type { VerdictResult } from '@/lib/types'
import { flagWeight, scoreBreakdown, sourceLabel } from '@/lib/verdict-explain'

function verdict(partial: Partial<VerdictResult>): VerdictResult {
  return {
    parcel_number: '1',
    verdict_version: 'v8',
    buildability_score: null,
    opportunity_score: 0,
    summary: '',
    can_build_by_right: null,
    by_right_units: null,
    max_height_ft: null,
    needs_variance: null,
    buildable_area_sqft: null,
    value_estimate_low: null,
    value_estimate_high: null,
    value_confidence: null,
    assessment_market_gap: null,
    arv: null,
    est_profit: null,
    est_margin: null,
    max_allowable_offer: null,
    deal_score: null,
    is_underpriced: null,
    risk_score: null,
    risk_flags: [],
    sources: [],
    field_trust: {},
    recommendation: null,
    recommendation_reason: null,
    decision_version: null,
    computed_at: '2026-07-11T00:00:00Z',
    ...partial,
  }
}

describe('scoreBreakdown', () => {
  it('blends 0.6 buildability + 0.4 (100 - risk)', () => {
    const b = scoreBreakdown(verdict({ buildability_score: 80, risk_score: 20 }))
    expect(b.buildabilityTerm).toBe(48)
    expect(b.riskInverse).toBe(80)
    expect(b.riskTerm).toBe(32)
    expect(b.total).toBe(80)
  })

  it('treats missing components as zero like the backend', () => {
    const b = scoreBreakdown(verdict({ buildability_score: null, risk_score: null }))
    expect(b.buildabilityTerm).toBe(0)
    expect(b.riskTerm).toBe(40)
    expect(b.total).toBe(40)
  })
})

describe('flagWeight', () => {
  it('maps severities to their risk weights', () => {
    expect(flagWeight('high')).toBe(40)
    expect(flagWeight('medium')).toBe(20)
    expect(flagWeight('low')).toBe(10)
    expect(flagWeight('info')).toBe(0)
    expect(flagWeight('unknown')).toBe(0)
  })
})

describe('sourceLabel', () => {
  it('humanizes known sources and passes through unknown', () => {
    expect(sourceLabel('tax_status')).toContain('Revenue')
    expect(sourceLabel('mystery_feed')).toBe('mystery_feed')
  })
})
