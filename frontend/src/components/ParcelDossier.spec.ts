import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ParcelDossier from '@/components/ParcelDossier.vue'
import type { DistressResult, DistressTier, ParcelDetail, VerdictResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'
import { usePipelineStore } from '@/stores/pipeline'
import { useWatchlistStore } from '@/stores/watchlist'

function makeDetail(overrides: Partial<ParcelDetail>): ParcelDetail {
  return {
    parcel_number: 'phl:141281340',
    market_code: 'phl',
    local_key: '141281340',
    address: '1123 LEMON ST',
    zip_code: '19123',
    owner: null,
    mailing_address: null,
    land_use: 'SINGLE FAMILY',
    category: null,
    base_zoning_code: 'RSA5',
    resolved_zoning_code: 'RSA5',
    zoning_resolution: 'attribute',
    market_value: 519000,
    land_value: 103800,
    improvement_value: 415200,
    exempt_land: null,
    exempt_building: null,
    assessment_year: 2026,
    assessment_ratio: 1.0,
    lot_area_sqft: 1342,
    lot_area_source: 'extract',
    condemned_status: null,
    frontage_ft: 20,
    depth_ft: 58,
    is_vacant: null,
    vacancy_confidence: null,
    is_city_owned: null,
    source: null,
    last_synced_at: null,
    longitude: null,
    latitude: null,
    ...overrides,
  }
}

const VERDICT: VerdictResult = {
  parcel_number: '141281340',
  opportunity_score: 76,
  buildability_score: 80,
  summary: 'RSA5: buildable by-right (1 unit)',
  can_build_by_right: true,
  by_right_units: 1,
  max_height_ft: 38,
  needs_variance: false,
  buildable_area_sqft: 490,
  value_estimate_low: 151197,
  value_estimate_high: 505487,
  value_confidence: 0.6,
  value_confidence_band: null,
  value_support_note: '',
  assessment_market_gap: -232130,
  arv: 550000,
  est_profit: -71208,
  est_margin: null,
  max_allowable_offer: null,
  deal_score: null,
  is_underpriced: null,
  risk_score: 40,
  risk_flags: [],
  sources: [],
  field_trust: {},
  recommendation: null,
  recommendation_reason: null,
  computed_at: '2026-07-04T00:00:00Z',
} as VerdictResult

function makeDistress(tier: DistressTier, score: number): DistressResult {
  return {
    parcel_number: 'phl:141281340',
    score,
    tier,
    factors: [{ code: 'tax_delinquent', label: 'Tax delinquent', weight: 30 }],
    sources: [],
    computed_at: '2026-07-28T00:00:00Z',
  }
}

function mountDossier(detail: ParcelDetail, distress: DistressResult | null = null) {
  const store = useParcelStore()
  store.detail = detail
  store.verdict = VERDICT
  store.distress = distress
  vi.spyOn(useWatchlistStore(), 'ensureLoaded').mockResolvedValue()
  vi.spyOn(usePipelineStore(), 'ensureLoaded').mockResolvedValue()
  return mount(ParcelDossier, {
    global: {
      plugins: [[Quasar, {}]],
      stubs: {
        SnapshotPanel: true,
        ChecklistPanel: true,
        DealCard: true,
        ScenariosPanel: true,
        CompsPanel: true,
        SubdivisionPanel: true,
        AssemblagePanel: true,
        HistoricPanel: true,
        PropertyFacts: true,
        DistressPanel: true,
        FreshnessPanel: true,
        ReportCorrectionDialog: true,
        OwnerPortfolioPanel: true,
        ReportPanel: true,
        DeedRestrictionsPanel: true,
        SheriffEvidence: true,
        DeedsEvidence: true,
        ViolationsEvidence: true,
        DelinquencyEvidence: true,
      },
    },
  })
}

describe('ParcelDossier developed-vs-vacant separation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('flags a built parcel as developed and hides the land-vs-assessment gap', () => {
    const wrapper = mountDossier(makeDetail({ land_use: 'SINGLE FAMILY', is_vacant: null }))
    expect(wrapper.find('.developed-banner').exists()).toBe(true)
    expect(wrapper.text()).toContain('Already developed')
    expect(wrapper.text()).not.toContain('vs. assessment')
    expect(wrapper.text()).toContain('Redevelopment land value')
  })

  it('treats a vacant lot as core inventory with no developed banner', () => {
    const wrapper = mountDossier(makeDetail({ land_use: 'VACANT LAND', is_vacant: true }))
    expect(wrapper.find('.developed-banner').exists()).toBe(false)
    expect(wrapper.text()).toContain('vs. assessment')
    expect(wrapper.text()).toContain('Estimated land value')
  })
})

describe('ParcelDossier seller-motivation surfacing', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  const vacant = () => makeDetail({ land_use: 'VACANT LAND', is_vacant: true })

  it('shows the motivation chip without a tab click when the owner is motivated', () => {
    const wrapper = mountDossier(vacant(), makeDistress('high', 72))
    const chip = wrapper.find('[data-test="motivation-chip"]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('High seller motivation')
    expect(chip.text()).toContain('72/100')
  })

  it('labels a medium tier as some motivation', () => {
    const wrapper = mountDossier(vacant(), makeDistress('medium', 41))
    expect(wrapper.find('[data-test="motivation-chip"]').text()).toContain('Some seller motivation')
  })

  it('stays silent rather than asserting a lot is unmotivated', () => {
    for (const tier of ['low', 'none'] as DistressTier[]) {
      const wrapper = mountDossier(vacant(), makeDistress(tier, 5))
      expect(wrapper.find('[data-test="motivation-chip"]').exists()).toBe(false)
    }
  })

  it('shows no chip where the market publishes no distress signal at all', () => {
    const wrapper = mountDossier(vacant(), null)
    expect(wrapper.find('[data-test="motivation-chip"]').exists()).toBe(false)
  })

  it('puts distress and its factors in the verdict, reachable without a click', () => {
    // Distress is a scored read on the owner, not a record of what is owed. It belongs
    // beside the verdict; the delinquency section shows the tax record itself.
    const wrapper = mountDossier(vacant(), makeDistress('high', 72))
    const verdict = wrapper.find('[data-test="lot-section-verdict-wrap"]')
    expect(verdict.exists()).toBe(true)
    expect(verdict.findComponent({ name: 'DistressPanel' }).exists()).toBe(true)
    const delinquency = wrapper.find('[data-test="lot-section-delinquency"]')
    expect(delinquency.findComponent({ name: 'DelinquencyEvidence' }).exists()).toBe(true)
  })
})

describe('ParcelDossier sections', () => {
  const vacantLot = () => makeDetail({ land_use: 'VACANT LAND', is_vacant: true })

  it('shows every section on one page, in order, without a tab click', () => {
    const wrapper = mountDossier(vacantLot())
    const html = wrapper.html()
    const order = [
      'lot-section-verdict-wrap',
      'lot-section-sheriff',
      'lot-section-deeds',
      'lot-section-violations',
      'lot-section-delinquency',
      'lot-section-comps',
      'lot-section-zoning',
      'lot-section-neighbors',
      'lot-section-corrections',
    ].map((id) => html.indexOf(id))

    expect(order.every((index) => index >= 0)).toBe(true)
    expect([...order].sort((a, b) => a - b)).toEqual(order)
  })

  it('gives the verdict section one deal card in place of the two retired panels', () => {
    const wrapper = mountDossier(vacantLot())
    const verdict = wrapper.find('[data-test="lot-section-verdict-wrap"]')
    expect(verdict.findComponent({ name: 'DealCard' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'DealPanel' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'UnderwritingPanel' }).exists()).toBe(false)
  })

  it('offers every section in the nav, on every lot', () => {
    // Including sheriff: "no listing is on file" is an answer, and a nav entry that comes
    // and goes is one a reader stops looking for.
    const wrapper = mountDossier(vacantLot())
    for (const id of ['verdict', 'sheriff', 'deeds', 'violations', 'delinquency', 'comps']) {
      expect(wrapper.find(`[data-test="lot-nav-${id}"]`).exists()).toBe(true)
    }
  })

  it('shows each record section with the evidence that answers it', () => {
    const wrapper = mountDossier(vacantLot())
    const pairs: [string, string][] = [
      ['lot-section-sheriff', 'SheriffEvidence'],
      ['lot-section-deeds', 'DeedsEvidence'],
      ['lot-section-violations', 'ViolationsEvidence'],
      ['lot-section-delinquency', 'DelinquencyEvidence'],
    ]
    for (const [section, component] of pairs) {
      expect(
        wrapper.find(`[data-test="${section}"]`).findComponent({ name: component }).exists(),
      ).toBe(true)
    }
  })

  it('anchors each section so a link can land on it', () => {
    const wrapper = mountDossier(vacantLot())
    for (const id of ['verdict', 'deeds', 'violations', 'delinquency', 'comps']) {
      expect(wrapper.find(`#${id}`).exists()).toBe(true)
    }
  })
})
