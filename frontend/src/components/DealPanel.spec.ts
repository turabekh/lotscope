import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import DealPanel from '@/components/DealPanel.vue'
import type { DealResult, ParcelDetail } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function deal(overrides: Partial<DealResult> = {}): DealResult {
  return {
    parcel_number: 'phl:000000001',
    units: 1,
    arv: 400000,
    per_unit_value: 400000,
    gross_floor_area_sqft: 1600,
    acquisition_cost: 60000,
    construction_cost: 280000,
    soft_cost: 28000,
    selling_cost: 24000,
    total_cost: 392000,
    profit: 8000,
    margin: 0.02,
    roi: 0.02,
    max_allowable_offer: 40000,
    is_underpriced: false,
    deal_score: 30,
    infeasible: false,
    comp_count: 5,
    confidence: 'medium',
    assumptions: {
      construction_cost_per_sqft: 175,
      soft_cost_pct: 0.1,
      selling_cost_pct: 0.06,
      target_margin: 0.2,
      default_unit_sqft: 1600,
      max_unit_sqft: 2400,
    },
    reasons: [],
    sources: [],
    computed_at: '2026-08-08T00:00:00Z',
    ...overrides,
  } as DealResult
}

function mountPanel(data: DealResult) {
  const store = useParcelStore()
  store.deal = data
  store.detail = { parcel_number: 'phl:000000001' } as ParcelDetail
  return mount(DealPanel, {
    global: {
      plugins: [[Quasar, {}]],
      stubs: {
        QTooltip: true,
        GenerateOfferDialog: {
          name: 'GenerateOfferDialog',
          props: ['maxAllowableOffer'],
          template: '<div />',
        },
      },
    },
  })
}

describe('DealPanel never presents an unbuildable deal as a price', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('states why no price works when the build does not pencil', () => {
    const wrapper = mountPanel(
      deal({ infeasible: true, max_allowable_offer: 0, profit: -120000, margin: -0.3 }),
    )

    const banner = wrapper.get('[data-test="deal-infeasible"]').text()
    expect(banner).toContain('not economical here at any land price')
    expect(banner).toContain('not an opportunity')
  })

  it('does not render a bare $0 that could read as a free lot', () => {
    const wrapper = mountPanel(deal({ infeasible: true, max_allowable_offer: 0 }))

    expect(wrapper.get('[data-test="deal-mao"]').text()).toBe('No viable price')
    expect(wrapper.get('[data-test="deal-mao"]').text()).not.toContain('$0')
  })

  it('never shows the underpriced banner alongside the infeasible one', () => {
    const wrapper = mountPanel(
      deal({ infeasible: true, is_underpriced: true, max_allowable_offer: 0 }),
    )

    expect(wrapper.find('[data-test="deal-infeasible"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('looks underpriced')
  })

  it('shows the price normally when the deal is feasible', () => {
    const wrapper = mountPanel(deal())

    expect(wrapper.find('[data-test="deal-infeasible"]').exists()).toBe(false)
    expect(wrapper.get('[data-test="deal-mao"]').text()).toBe('$40,000')
  })

  it('does not seed the offer dialog with a price on an unbuildable deal', () => {
    const wrapper = mountPanel(deal({ infeasible: true, max_allowable_offer: 0 }))
    const dialog = wrapper.findComponent({ name: 'GenerateOfferDialog' })

    expect(dialog.props('maxAllowableOffer')).toBeNull()
  })

  it('seeds the offer dialog from the max allowable offer when the deal is feasible', () => {
    const wrapper = mountPanel(deal())
    const dialog = wrapper.findComponent({ name: 'GenerateOfferDialog' })

    expect(dialog.props('maxAllowableOffer')).toBe(40000)
  })
})
