import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import DataCoverageChip from '@/components/DataCoverageChip.vue'
import { MARKET_LABELS, useMarketStore } from '@/stores/market'

describe('DataCoverageChip', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  function mountChip() {
    return mount(DataCoverageChip, { global: { plugins: [[Quasar, {}]] } })
  }

  function withStatus(launchStatus: string) {
    const store = useMarketStore()
    store.infos = [
      {
        code: 'phl',
        name: 'Philadelphia',
        state: 'PA',
        url_slug: store.active,
        map_center: [0, 0],
        map_bounds: null,
        default_zoom: 12,
        launch_status: launchStatus,
        coverage_note: null,
        hidden_surfaces: [],
        risk_coverage_note: null,
        forced_sale_surface_label: 'Sheriff sales',
      },
    ] as never
    return store
  }

  it('renders the active market label from the store, not a hardcoded city', () => {
    withStatus('live')
    const wrapper = mountChip()
    expect(wrapper.text()).toContain(MARKET_LABELS[useMarketStore().active])
    expect(wrapper.text()).toContain('flagship')
  })

  it('marks a pilot market as a pilot rather than as the flagship', () => {
    withStatus('pilot')
    expect(mountChip().text()).toContain('pilot')
  })

  it('says nothing at all until the market status is known', () => {
    expect(mountChip().text()).toBe('')
  })
})
