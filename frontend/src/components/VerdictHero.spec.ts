import { mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { describe, expect, it } from 'vitest'

import VerdictHero from '@/components/VerdictHero.vue'
import type { VerdictResult } from '@/lib/types'

function makeVerdict(overrides: Partial<VerdictResult>): VerdictResult {
  return {
    parcel_number: '000000001',
    verdict_version: 'v8',
    buildability_score: 40,
    opportunity_score: 55,
    summary: 'RSA-5: variance likely',
    can_build_by_right: false,
    by_right_units: 1,
    max_height_ft: 38,
    needs_variance: true,
    buildable_area_sqft: 490,
    value_estimate_low: 150000,
    value_estimate_high: 320000,
    value_confidence: 0.6,
    assessment_market_gap: null,
    arv: null,
    est_profit: null,
    est_margin: null,
    max_allowable_offer: null,
    deal_score: null,
    is_underpriced: null,
    risk_score: 20,
    risk_flags: [],
    sources: [],
    computed_at: '2026-07-05T00:00:00Z',
    ...overrides,
  } as VerdictResult
}

describe('VerdictHero buildability gating', () => {
  it('shows "Variance likely" for a not-by-right parcel even when by_right_units is set', () => {
    const wrapper = mount(VerdictHero, {
      props: { verdict: makeVerdict({ can_build_by_right: false, needs_variance: true }) },
      global: { plugins: [[Quasar, {}]] },
    })
    expect(wrapper.text()).toContain('Variance likely')
    expect(wrapper.text()).not.toContain('By-right')
  })

  it('shows the by-right unit count when the parcel is buildable by-right', () => {
    const wrapper = mount(VerdictHero, {
      props: {
        verdict: makeVerdict({ can_build_by_right: true, needs_variance: false, by_right_units: 1 }),
      },
      global: { plugins: [[Quasar, {}]] },
    })
    expect(wrapper.text()).toContain('By-right')
    expect(wrapper.text()).not.toContain('Variance likely')
  })
})
