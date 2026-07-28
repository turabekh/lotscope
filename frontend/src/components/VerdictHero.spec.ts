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
    expect(text).toContain('Not a construction approval')
    expect(text).not.toContain('Developable under Title 14')
    expect(text).not.toContain('Variance likely')
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
