import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import VerdictPanel from '@/components/VerdictPanel.vue'
import type { ParcelChecklist, VerdictResult } from '@/lib/types'

function makeVerdict(overrides: Partial<VerdictResult>): VerdictResult {
  return {
    parcel_number: 'phl:000000001',
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

function makeChecklist(overrides: Partial<ParcelChecklist> = {}): ParcelChecklist {
  return {
    parcel_number: 'phl:000000001',
    posture: null,
    items: [
      {
        code: 'access',
        label: 'Access & frontage',
        category: 'Access & frontage',
        status: 'not_evaluated',
        detail: '',
        source: null,
      },
    ],
    summary: { not_evaluated: 1, passed: 0, warnings: 0, failures: 0, info: 0, ready: true },
    buildability_confidence: 'high',
    buildability_confidence_reasons: [],
    program: null,
    computed_at: '2026-08-01T00:00:00Z',
    ...overrides,
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

describe('buildability confidence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the confidence label on the buildability card', () => {
    const wrapper = mountPanel(makeVerdict({}), makeChecklist())
    const chip = wrapper.find('[data-test="buildability-confidence"]')

    expect(chip.exists()).toBe(true)
    expect(chip.isVisible()).toBe(true)
    expect(chip.text()).toContain('High confidence')
  })

  it('names the unverified inputs outside any tooltip when confidence is not high', () => {
    const wrapper = mountPanel(
      makeVerdict({}),
      makeChecklist({
        buildability_confidence: 'medium',
        buildability_confidence_reasons: [
          'No by-right height standard is recorded for this district, so the vertical envelope is unverified.',
        ],
      }),
    )
    const chip = wrapper.find('[data-test="buildability-confidence"]')
    const reasons = wrapper.find('[data-test="confidence-reasons"]')

    expect(chip.text()).toContain('Medium confidence')
    expect(reasons.exists()).toBe(true)
    expect(reasons.isVisible()).toBe(true)
    expect(reasons.text()).toContain('vertical envelope is unverified')
  })

  it('lists no reasons when every input is verified', () => {
    const wrapper = mountPanel(makeVerdict({}), makeChecklist())
    expect(wrapper.find('[data-test="confidence-reasons"]').exists()).toBe(false)
  })

  it('shows nothing when the checklist has not loaded', () => {
    const wrapper = mountPanel(makeVerdict({}), null)
    expect(wrapper.find('[data-test="buildability-confidence"]').exists()).toBe(false)
  })
})

describe('wide-area land value', () => {
  const WIDE_SOURCES = [
    {
      dimension: 'valuation',
      sources: [{ source: 'rtt_summary', comp_tier: 'wide_area', radius_ft: 3000, years: 5 }],
    },
  ]

  it('tells the reader the estimate came from a wider search', () => {
    const wrapper = mountPanel(makeVerdict({ sources: WIDE_SOURCES }))
    const note = wrapper.find('[data-test="wide-area-note"]')

    expect(note.exists()).toBe(true)
    expect(note.isVisible()).toBe(true)
    expect(note.text()).toContain('3,000 ft')
    expect(note.text()).toContain('rough guide')
  })

  it('says nothing when the comps were local', () => {
    const wrapper = mountPanel(
      makeVerdict({
        sources: [
          { dimension: 'valuation', sources: [{ comp_tier: 'local', radius_ft: 1500, years: 3 }] },
        ],
      }),
    )

    expect(wrapper.find('[data-test="wide-area-note"]').exists()).toBe(false)
  })

  it('does not show the note when there is no estimate at all', () => {
    const wrapper = mountPanel(
      makeVerdict({
        value_estimate_low: null,
        value_estimate_high: null,
        sources: WIDE_SOURCES,
      }),
    )

    expect(wrapper.find('[data-test="wide-area-note"]').exists()).toBe(false)
  })
})

describe('unit count never contradicts the buildability headline', () => {
  it('does not label the count by-right on a lot that needs a variance', () => {
    const wrapper = mountPanel(
      makeVerdict({ can_build_by_right: false, needs_variance: true, by_right_units: 2 }),
    )

    expect(wrapper.get('[data-test="unit-label"]').text()).toBe('Units if a variance is granted')
    expect(wrapper.get('[data-test="unit-value"]').text()).toBe('2')
    expect(wrapper.get('[data-test="unit-label"]').text()).not.toContain('By-right')
    expect(wrapper.text()).toContain('Variance likely')
  })

  it('shows no unit number at all for a master-plan district', () => {
    const wrapper = mountPanel(
      makeVerdict({ can_build_by_right: false, needs_variance: false, by_right_units: 4 }),
      makeChecklist({ posture: 'master_plan_required' }),
    )

    expect(wrapper.get('[data-test="unit-value"]').text()).toBe('None')
    expect(wrapper.get('[data-test="unit-value"]').text()).not.toContain('4')
    expect(wrapper.text()).toContain('Master plan required')
    expect(wrapper.text()).not.toContain('Buildability uncertain')
  })

  it('keeps the plain by-right label when the lot is eligible', () => {
    const wrapper = mountPanel(makeVerdict({}), makeChecklist())

    expect(wrapper.get('[data-test="unit-label"]').text()).toBe('By-right units')
    expect(wrapper.get('[data-test="unit-value"]').text()).toBe('1')
  })

  it('does not promise by-right units when conformance is unresolved', () => {
    const wrapper = mountPanel(
      makeVerdict({ can_build_by_right: null, needs_variance: null, by_right_units: 3 }),
    )

    expect(wrapper.get('[data-test="unit-label"]').text()).not.toContain('By-right')
    expect(wrapper.get('[data-test="unit-label"]').text()).toBe('Units the standards would support')
  })
})
