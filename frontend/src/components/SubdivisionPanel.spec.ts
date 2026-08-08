import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import SubdivisionPanel from '@/components/SubdivisionPanel.vue'
import type { SubdivisionResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function subdivision(overrides: Partial<SubdivisionResult> = {}): SubdivisionResult {
  return {
    parcel_number: 'phl:000000001',
    district_code: 'RSA-5',
    can_subdivide: false,
    max_lots: null,
    limiting_factor: null,
    is_conforming: null,
    needs_consolidation: false,
    lot_area_sqft: 2000,
    lot_width_ft: 20,
    min_lot_area_sqft: null,
    min_lot_width_ft: null,
    reasons: ['No dimensional minimums are recorded for this district.'],
    sources: [],
    computed_at: '2026-08-08T00:00:00Z',
    ...overrides,
  } as SubdivisionResult
}

function render(value: SubdivisionResult | null) {
  setActivePinia(createPinia())
  const store = useParcelStore()
  store.subdivision = value
  return mount(SubdivisionPanel, { global: { plugins: [Quasar] } })
}

describe('SubdivisionPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('says so when the analysis could not be evaluated', () => {
    const wrapper = render(subdivision())

    expect(wrapper.text()).toContain('Not evaluated')
    expect(wrapper.text()).toContain('No dimensional minimums are recorded for this district.')
    expect(wrapper.text()).toContain('a gap in what we hold')
  })

  it('does not call an unevaluated lot a consolidation candidate', () => {
    const wrapper = render(subdivision())

    expect(wrapper.text()).not.toContain('Consolidation candidate')
    expect(wrapper.text()).not.toContain('Splits into')
  })

  it('still reports a lot that can be split', () => {
    const wrapper = render(
      subdivision({
        can_subdivide: true,
        max_lots: 3,
        is_conforming: true,
        min_lot_area_sqft: 1440,
        min_lot_width_ft: 16,
        reasons: ['Lot is large enough for up to 3 conforming lots.'],
      }),
    )

    expect(wrapper.text()).toContain('Splits into 3 lots')
    expect(wrapper.text()).not.toContain('Not evaluated')
    expect(wrapper.text()).not.toContain('a gap in what we hold')
  })

  it('still reports a consolidation candidate', () => {
    const wrapper = render(
      subdivision({
        needs_consolidation: true,
        max_lots: 0,
        is_conforming: false,
        min_lot_area_sqft: 1440,
        reasons: ['Lot is below the district minimums.'],
      }),
    )

    expect(wrapper.text()).toContain('Consolidation candidate')
    expect(wrapper.text()).not.toContain('Not evaluated')
  })

  it('reports a lot that meets the minimums but cannot be split', () => {
    const wrapper = render(
      subdivision({
        can_subdivide: false,
        needs_consolidation: false,
        max_lots: 1,
        is_conforming: true,
        min_lot_area_sqft: 1440,
        min_lot_width_ft: 16,
        reasons: ['Lot meets the district minimums but is not large enough to split.'],
      }),
    )

    expect(wrapper.text()).toContain('Too small to split')
    expect(wrapper.text()).toContain('not large enough to split')
    expect(wrapper.text()).not.toContain('Not evaluated')
    expect(wrapper.text()).not.toContain('a gap in what we hold')
  })

  it('renders nothing when there is no subdivision result at all', () => {
    const wrapper = render(null)

    expect(wrapper.text()).toBe('')
  })
})
