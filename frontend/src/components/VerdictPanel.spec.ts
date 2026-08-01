import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import VerdictPanel from '@/components/VerdictPanel.vue'
import type { ParcelChecklist, VerdictResult } from '@/lib/types'

function makeVerdict(overrides: Partial<VerdictResult>): VerdictResult {
  return {
    parcel_number: 'phl:000000001',
    verdict_version: 'v8',
    buildability_score: 60,
    opportunity_score: 55,
    summary: 'RSA-5',
    can_build_by_right: true,
    by_right_units: 1,
    max_height_ft: 38,
    needs_variance: false,
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
    risk_score: 10,
    risk_flags: [],
    sources: [],
    computed_at: '2026-08-01T00:00:00Z',
    ...overrides,
  } as VerdictResult
}

function makeChecklist(): ParcelChecklist {
  return {
    parcel_number: 'phl:000000001',
    items: [
      {
        code: 'access',
        category: 'Access & frontage',
        status: 'not_evaluated',
        detail: '',
        source: null,
      },
    ],
    summary: { not_evaluated: 1, passed: 0, warnings: 0, failures: 0, info: 0, ready: true },
    computed_at: '2026-08-01T00:00:00Z',
  }
}

function mountPanel(verdict: VerdictResult, checklist: ParcelChecklist | null = null) {
  return mount(VerdictPanel, {
    props: { verdict, checklist },
    global: {
      plugins: [[Quasar, {}]],
      stubs: { QTooltip: true, VarianceOutlookLine: true },
    },
  })
}

describe('VerdictPanel buildability qualifier', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the qualifier outside any tooltip', () => {
    const wrapper = mountPanel(makeVerdict({}), makeChecklist())
    const qualifier = wrapper.find('[data-test="build-qualifier"]')
    expect(qualifier.exists()).toBe(true)
    expect(qualifier.text()).toContain('preliminary screening, not a construction approval')
    expect(qualifier.text()).toContain('Still to check: Access & frontage.')
  })

  it('states plainly when the base-district standards are not met', () => {
    const wrapper = mountPanel(makeVerdict({ can_build_by_right: false, needs_variance: true }))
    const text = wrapper.find('[data-test="build-qualifier"]').text()
    expect(text).toContain('variance or special exception')
    expect(text).not.toContain('Still to check')
  })

  it('does not claim buildability could be evaluated when it could not', () => {
    const wrapper = mountPanel(makeVerdict({ can_build_by_right: null, needs_variance: false }))
    expect(wrapper.find('[data-test="build-qualifier"]').text()).toContain('could not be evaluated')
  })

  it('never presents the base-district pass as an approval', () => {
    const text = mountPanel(makeVerdict({}), makeChecklist()).text().toLowerCase()
    expect(text).not.toContain('buildable by right')
    expect(text).not.toContain('approved')
  })
})
