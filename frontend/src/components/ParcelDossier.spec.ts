import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ParcelDossier from '@/components/ParcelDossier.vue'
import type { ParcelDetail, VerdictResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'
import { usePipelineStore } from '@/stores/pipeline'
import { useWatchlistStore } from '@/stores/watchlist'

function makeDetail(overrides: Partial<ParcelDetail>): ParcelDetail {
  return {
    parcel_number: '141281340',
    address: '1123 LEMON ST',
    zip_code: '19123',
    owner: null,
    mailing_address: null,
    land_use: 'SINGLE FAMILY',
    category: null,
    base_zoning_code: 'RSA5',
    market_value: 519000,
    land_value: 103800,
    improvement_value: 415200,
    exempt_land: null,
    exempt_building: null,
    assessment_year: 2026,
    lot_area_sqft: 1342,
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
  verdict_version: 'v7',
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
  computed_at: '2026-07-04T00:00:00Z',
} as VerdictResult

function mountDossier(detail: ParcelDetail) {
  const store = useParcelStore()
  store.detail = detail
  store.verdict = VERDICT
  vi.spyOn(useWatchlistStore(), 'ensureLoaded').mockResolvedValue()
  vi.spyOn(usePipelineStore(), 'ensureLoaded').mockResolvedValue()
  return mount(ParcelDossier, {
    global: {
      plugins: [[Quasar, {}]],
      stubs: {
        SnapshotPanel: true,
        ChecklistPanel: true,
        DealPanel: true,
        ScenariosPanel: true,
        CompsPanel: true,
        AssessmentPanel: true,
        MarketContextPanel: true,
        SubdivisionPanel: true,
        AssemblagePanel: true,
        HistoricPanel: true,
        PropertyFacts: true,
        DistressPanel: true,
        OwnerPortfolioPanel: true,
        ReportPanel: true,
        DeedRestrictionsPanel: true,
        AskBox: true,
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
