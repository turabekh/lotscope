import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import OverlayPanel from '@/components/OverlayPanel.vue'
import type { SubdivisionResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function subdivision(overlays: string[]): SubdivisionResult {
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
    overlays,
    reasons: [],
    sources: [],
    computed_at: '2026-08-11T00:00:00Z',
  } as SubdivisionResult
}

function render(value: SubdivisionResult | null) {
  setActivePinia(createPinia())
  const store = useParcelStore()
  store.subdivision = value
  return mount(OverlayPanel, { global: { plugins: [Quasar] } })
}

describe('OverlayPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('names every overlay the parcel sits in', () => {
    const wrapper = render(
      subdivision([
        '/NDO Ninth District Overlay District',
        '/FDO Fourth District Overlay District',
      ]),
    )

    expect(wrapper.find('[data-test="overlay-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('/NDO Ninth District Overlay District')
    expect(wrapper.text()).toContain('/FDO Fourth District Overlay District')
  })

  it('warns that overlay standards can override the base minimums', () => {
    const wrapper = render(subdivision(['/EDO Eighth District Overlay District']))

    expect(wrapper.text()).toContain('override the base-district minimums')
  })

  it('renders nothing when the parcel is in no overlay', () => {
    const wrapper = render(subdivision([]))

    expect(wrapper.find('[data-test="overlay-panel"]').exists()).toBe(false)
  })

  it('renders nothing when subdivision data is absent', () => {
    const wrapper = render(null)

    expect(wrapper.find('[data-test="overlay-panel"]').exists()).toBe(false)
  })
})
