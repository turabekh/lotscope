import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import DiscoverySources from '@/components/DiscoverySources.vue'
import { routes } from '@/router'
import { useMarketStore } from '@/stores/market'
import type { MarketInfo } from '@/lib/types'

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

async function mountSources(): Promise<ReturnType<typeof mount>> {
  const router: Router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(DiscoverySources, {
    global: { plugins: [router, [Quasar, {}]] },
  })
  await router.isReady()
  return wrapper
}

describe('DiscoverySources', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('links the consolidated discovery surfaces for the active market', async () => {
    const html = (await mountSources()).html()
    expect(html).toContain('href="/philadelphia/feed"')
    expect(html).toContain('href="/philadelphia/sheriff-sales"')
    expect(html).toContain('href="/philadelphia/top-plays"')
  })

  it('uses the market forced-sale label', async () => {
    const store = useMarketStore()
    store.infos = [
      makeMarket({}),
      makeMarket({
        code: 'hbg',
        url_slug: 'harrisburg',
        launch_status: 'pilot',
        forced_sale_surface_label: 'Tax sales',
      }),
    ]
    store.active = 'harrisburg'
    const wrapper = await mountSources()
    expect(wrapper.text()).toContain('Tax sales')
    expect(wrapper.text()).not.toContain('Sheriff sales')
  })

  it('omits surfaces the market hides', async () => {
    const store = useMarketStore()
    store.infos = [makeMarket({ hidden_surfaces: ['sheriff_sales', 'top_plays'] })]
    store.active = 'philadelphia'
    const wrapper = await mountSources()
    expect(wrapper.html()).toContain('href="/philadelphia/feed"')
    expect(wrapper.html()).not.toContain('href="/philadelphia/sheriff-sales"')
    expect(wrapper.html()).not.toContain('href="/philadelphia/top-plays"')
  })
})
