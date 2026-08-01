import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import MarketSwitcher from '@/components/MarketSwitcher.vue'
import { routes } from '@/router'
import { useMarketStore } from '@/stores/market'

function mountPill(compact: boolean) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  return mount(MarketSwitcher, {
    props: { variant: 'pill', compact },
    global: { plugins: [router, [Quasar, {}]] },
  })
}

function setMarket(launchStatus: string): void {
  const market = useMarketStore()
  market.active = 'philadelphia'
  market.infos = [
    {
      code: 'phl',
      name: 'Philadelphia',
      state: 'PA',
      url_slug: 'philadelphia',
      map_center: [-75.16, 39.95],
      map_bounds: null,
      default_zoom: 12,
      launch_status: launchStatus,
      coverage_note: null,
      hidden_surfaces: [],
      risk_coverage_note: null,
      forced_sale_surface_label: 'Sheriff sales',
    },
  ] as never
}

describe('MarketSwitcher pill', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the market code when space is tight', () => {
    setMarket('live')
    expect(mountPill(true).text()).toContain('PHL')
  })

  it('shows the full name when there is room', () => {
    setMarket('live')
    expect(mountPill(false).text()).toContain('Philadelphia')
  })

  it('drops the flagship badge, which only decorates', () => {
    setMarket('live')
    expect(mountPill(true).find('[data-test="active-market-status"]').exists()).toBe(false)
  })

  it('keeps the pilot badge, which warns', () => {
    setMarket('pilot')
    const badge = mountPill(true).find('[data-test="active-market-status"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('pilot')
  })
})
