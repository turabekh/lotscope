import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import VerdictHero from '@/components/VerdictHero.vue'
import type { MarketInfo, VerdictResult } from '@/lib/types'
import { useMarketStore } from '@/stores/market'

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

function makeMarket(overrides: Partial<MarketInfo>): MarketInfo {
  return {
    code: 'phl',
    name: 'Philadelphia',
    state: 'PA',
    url_slug: 'philadelphia',
    map_center: [-75.16, 39.95],
    map_bounds: null,
    default_zoom: 12,
    launch_status: 'live',
    coverage_note: null,
    hidden_surfaces: [],
    risk_coverage_note: null,
    forced_sale_surface_label: 'Sheriff sales',
    ...overrides,
  }
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
          items: [
            {
              code: 'access',
              category: 'Access & frontage',
              status: 'not_evaluated',
              detail: '',
              source: null,
            },
            {
              code: 'liens',
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

  it('qualifies the clean risk pillar with the coverage note of the parcel market', () => {
    const store = useMarketStore()
    store.active = 'harrisburg'
    store.infos = [
      makeMarket({
        code: 'hbg',
        url_slug: 'harrisburg',
        launch_status: 'pilot',
        risk_coverage_note: 'based on available Harrisburg sources',
      }),
    ]
    const wrapper = mountHero(
      makeVerdict({ parcel_number: 'hbg:000000001', risk_score: 0, risk_flags: [] }),
    )
    expect(wrapper.text()).toContain('based on available Harrisburg sources')
  })

  it('leaves the clean risk pillar unqualified for a market with full coverage', () => {
    const store = useMarketStore()
    store.active = 'philadelphia'
    store.infos = [makeMarket({ risk_coverage_note: null })]
    const wrapper = mountHero(makeVerdict({ risk_score: 0, risk_flags: [] }))
    expect(wrapper.text()).toContain('No major risk flags found')
    expect(wrapper.text()).not.toContain('based on available')
  })

  it('does not leak the active market note onto a parcel from another market', () => {
    const store = useMarketStore()
    store.active = 'harrisburg'
    store.infos = [
      makeMarket({ code: 'phl', url_slug: 'philadelphia', risk_coverage_note: null }),
      makeMarket({
        code: 'hbg',
        url_slug: 'harrisburg',
        launch_status: 'pilot',
        risk_coverage_note: 'based on available Harrisburg sources',
      }),
    ]
    const wrapper = mountHero(
      makeVerdict({ parcel_number: 'phl:875100090', risk_score: 0, risk_flags: [] }),
    )
    expect(wrapper.text()).toContain('No major risk flags found')
    expect(wrapper.text()).not.toContain('based on available Harrisburg sources')
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
