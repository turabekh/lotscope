import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import VerdictHero from '@/components/VerdictHero.vue'
import type { ParcelChecklist, VerdictResult } from '@/lib/types'

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

function mountHero(verdict: VerdictResult) {
  return mount(VerdictHero, {
    props: { verdict },
    global: {
      plugins: [[Quasar, {}]],
      stubs: { QTooltip: { template: '<div class="q-tooltip-stub"><slot /></div>' } },
    },
  })
}

describe('VerdictHero', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows "Variance likely" for a not-by-right parcel even when by_right_units is set', () => {
    const wrapper = mountHero(makeVerdict({ can_build_by_right: false, needs_variance: true }))
    expect(wrapper.text()).toContain('Variance likely')
    expect(wrapper.text()).not.toContain('By-right')
  })

  it('reports base-district eligibility without promising construction approval', () => {
    const wrapper = mountHero(
      makeVerdict({ can_build_by_right: true, needs_variance: false, by_right_units: 1 }),
    )
    const text = wrapper.text()
    expect(text).toContain('Base district · 1 unit')
    expect(text).toContain('dimensionally eligible')
    expect(text).toContain('preliminary screening, not a construction approval')
    expect(text).toContain('Still to check')
    expect(text).not.toContain('Developable under Title 14')
    expect(text).not.toContain('Variance likely')
  })

  it('names the outstanding checks beside the eligibility claim', () => {
    const wrapper = mount(VerdictHero, {
      props: {
        verdict: makeVerdict({
          can_build_by_right: true,
          needs_variance: false,
          by_right_units: 2,
        }),
        checklist: {
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
            {
              code: 'liens',
              label: 'Liens & taxes',
              category: 'Liens & taxes',
              status: 'pass',
              detail: '',
              source: null,
            },
          ],
          summary: {
            not_evaluated: 1,
            passed: 1,
            warnings: 0,
            failures: 0,
            info: 0,
            ready: true,
          },
          buildability_confidence: 'high',
          buildability_confidence_reasons: [],
          program: null,
          computed_at: '2026-08-01T00:00:00Z',
        },
      },
      global: {
        plugins: [[Quasar, {}]],
        stubs: { QTooltip: { template: '<div class="q-tooltip-stub"><slot /></div>' } },
      },
    })
    const text = wrapper.text()
    expect(text).toContain('Still to check: Access & frontage.')
    expect(text).not.toContain('Liens & taxes')
  })

  it('never states an unconditional by-right permission', () => {
    for (const verdict of [
      makeVerdict({ can_build_by_right: true, needs_variance: false }),
      makeVerdict({ can_build_by_right: false, needs_variance: true }),
      makeVerdict({ can_build_by_right: null, needs_variance: false }),
    ]) {
      const text = mountHero(verdict).text().toLowerCase()
      expect(text).not.toContain('buildable by right')
      expect(text).not.toContain('can build by right')
      expect(text).not.toContain('approved')
    }
  })
})

describe('VerdictHero screening result', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('leads with the screening result and its reason, not the composite score', () => {
    const wrapper = mountHero(
      makeVerdict({
        recommendation: 'strong_candidate',
        recommendation_reason: 'Appears dimensionally eligible with a projected margin of 24%.',
      }),
    )
    const text = wrapper.text()
    expect(text).toContain('Screening result')
    expect(text).toContain('Strong candidate')
    expect(text).toContain('projected margin of 24%')
  })

  it('says a parcel is not yet screened rather than inventing a result', () => {
    const wrapper = mountHero(makeVerdict({ recommendation: null, recommendation_reason: null }))
    expect(wrapper.find('[data-test="no-recommendation"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Strong candidate')
  })

  it('never presents insufficient data as a positive result', () => {
    const wrapper = mountHero(
      makeVerdict({
        recommendation: 'insufficient_data',
        recommendation_reason: 'Core buildability could not be established.',
      }),
    )
    const text = wrapper.text()
    expect(text).toContain('Insufficient data')
    expect(text).not.toContain('Strong candidate')
  })

  it('surfaces at most three deal killers in the hero', () => {
    const wrapper = mountHero(
      makeVerdict({
        recommendation: 'worth_investigating',
        risk_flags: [
          {
            code: 'no_street_access',
            label: 'No street access',
            severity: 'high',
            detail: '',
            source: '',
          },
          {
            code: 'tax_delinquent',
            label: 'Tax delinquent',
            severity: 'high',
            detail: '',
            source: '',
          },
          {
            code: 'flood_zone',
            label: 'Flood zone',
            severity: 'medium',
            detail: '',
            source: '',
          },
          {
            code: 'historic_district',
            label: 'Historic',
            severity: 'medium',
            detail: '',
            source: '',
          },
        ],
      }),
    )
    const chips = wrapper.find('[data-test="deal-killers"]').findAllComponents({ name: 'QChip' })
    expect(chips.length).toBe(3)
    expect(wrapper.text()).toContain('No street access')
  })

  it('keeps the opportunity score reachable but demoted', () => {
    const wrapper = mountHero(makeVerdict({ recommendation: 'worth_investigating' }))
    expect(wrapper.text()).toContain('Opportunity score')
  })
})

describe('VerdictHero never contradicts the checks beneath it', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function mountWithChecklist(verdict: VerdictResult, checklist: ParcelChecklist) {
    return mount(VerdictHero, {
      props: { verdict, checklist },
      global: {
        plugins: [[Quasar, {}]],
        stubs: { QTooltip: { template: '<div class="q-tooltip-stub"><slot /></div>' } },
      },
    })
  }

  const checklistWith = (
    items: ParcelChecklist['items'],
    posture: ParcelChecklist['posture'] = null,
  ): ParcelChecklist => ({
    parcel_number: 'phl:000000001',
    posture,
    items,
    summary: {
      passed: 0,
      warnings: items.filter((i) => i.status === 'potential_issue').length,
      failures: items.filter((i) => i.status === 'fail').length,
      info: 0,
      not_evaluated: items.filter((i) => i.status === 'not_evaluated').length,
      ready: false,
    },
    program: null,
    buildability_confidence: 'high',
    buildability_confidence_reasons: [],
    computed_at: '2026-08-01T00:00:00Z',
  })

  it('names a failing check under a by-right headline instead of only listing unknowns', () => {
    const wrapper = mountWithChecklist(
      makeVerdict({ can_build_by_right: true, by_right_units: 2 }),
      checklistWith([
        {
          code: 'li',
          label: 'L&I & demolition',
          category: 'Risk',
          status: 'fail',
          detail: 'Unsafe structure on record.',
          source: null,
        },
      ]),
    )

    expect(wrapper.text()).toContain('Flagged for a closer look: L&I & demolition')
    expect(wrapper.text()).toContain('this eligibility may not hold')
  })

  it('does not advertise base-district units on a master-plan lot', () => {
    const wrapper = mountWithChecklist(
      makeVerdict({ can_build_by_right: true, by_right_units: 3 }),
      checklistWith([], 'master_plan_required'),
    )

    expect(wrapper.text()).toContain('Master plan required')
    expect(wrapper.text()).not.toContain('Base district · 3 units')
    expect(wrapper.text()).toContain('not permitted by right')
  })
})

describe('VerdictHero value pillar states how well the estimate is supported', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('does not claim the sales were nearby when confidence is low', () => {
    const wrapper = mountHero(
      makeVerdict({
        value_estimate_low: 100000,
        value_estimate_high: 200000,
        value_confidence: 0.3,
        value_confidence_band: 'low',
        value_support_note:
          'The supporting sales are few, widely spread, or drawn from a wider search because none were found close by. Treat this as a rough guide, not a market read for this block.',
      }),
    )

    expect(wrapper.text()).toContain('rough guide')
    expect(wrapper.text()).not.toContain('recent recorded comparable sales nearby')
  })

  it('prefers the specific wider-search note over the generic one', () => {
    const wrapper = mountHero(
      makeVerdict({
        value_estimate_low: 100000,
        value_estimate_high: 200000,
        value_confidence: 0.3,
        value_confidence_band: 'low',
        value_support_note: 'generic fallback note',
        sources: [
          {
            dimension: 'valuation',
            sources: [{ source: 'rtt_summary', comp_tier: 'wide_area', radius_ft: 3000, years: 5 }],
          },
        ],
      }),
    )

    expect(wrapper.text()).toContain('No land sales were found close by')
    expect(wrapper.text()).toContain('3,000 ft away')
    expect(wrapper.text()).not.toContain('generic fallback note')
  })

  it('states plainly when there is no estimate rather than implying a weak one', () => {
    const wrapper = mountHero(
      makeVerdict({
        value_estimate_low: null,
        value_estimate_high: null,
        value_confidence: null,
        value_confidence_band: null,
        value_support_note: 'Not enough recorded comparable sales nearby yet.',
      }),
    )

    expect(wrapper.text()).toContain('No comps')
    expect(wrapper.text()).toContain('Not enough recorded comparable sales nearby yet.')
  })
})
