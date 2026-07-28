import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import AppSidebar from '@/components/AppSidebar.vue'
import { routes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'
import type { MarketInfo, User } from '@/lib/types'

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

function makeRouter(): Router {
  return createRouter({ history: createMemoryHistory(), routes })
}

function setUser(role: 'user' | 'admin'): void {
  useAuthStore().user = { id: 1, email: 't@x.co', role, tier: 'free' } as unknown as User
}

async function mountSidebar(router: Router) {
  const wrapper = mount(AppSidebar, {
    props: { collapsed: false },
    global: { plugins: [router, [Quasar, {}]] },
  })
  await router.isReady()
  return wrapper
}

describe('AppSidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders scoped nav links carrying the active market', async () => {
    setUser('user')
    const router = makeRouter()
    const wrapper = await mountSidebar(router)
    const html = wrapper.html()
    expect(html).toContain('href="/philadelphia/home"')
    expect(html).toContain('href="/philadelphia/explore"')
    expect(html).toContain('href="/philadelphia/leads"')
    expect(html).toContain('href="/philadelphia/lists"')
    expect(html).toContain('href="/account"')
  })

  it('marks the active section from the current route', async () => {
    setUser('user')
    const router = makeRouter()
    await router.push({ name: 'leads', params: { market: 'philadelphia' } })
    const wrapper = await mountSidebar(router)
    expect(wrapper.find('.nav-active').text()).toContain('Leads')
  })

  it('labels the forced-sale nav item per market', async () => {
    setUser('user')
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

    store.active = 'philadelphia'
    const phl = await mountSidebar(makeRouter())
    expect(phl.text()).toContain('Sheriff sales')
    expect(phl.text()).not.toContain('Tax sales')

    store.active = 'harrisburg'
    const hbg = await mountSidebar(makeRouter())
    expect(hbg.text()).toContain('Tax sales')
    expect(hbg.text()).not.toContain('Sheriff sales')
  })

  it('hides Admin for non-admins and shows it for admins', async () => {
    const router = makeRouter()

    setUser('user')
    const asUser = await mountSidebar(router)
    expect(asUser.text()).not.toContain('Admin')

    setUser('admin')
    const asAdmin = await mountSidebar(router)
    expect(asAdmin.text()).toContain('Admin')
  })

  it('keeps primary navigation to five destinations', async () => {
    setUser('user')
    const wrapper = await mountSidebar(makeRouter())
    const primary = wrapper.findAll('[data-test="nav-primary"] > .nav-item')
    expect(primary).toHaveLength(5)
    const labels = primary.map((item) => item.text())
    ;['Home', 'Find lots', 'Leads', 'Pipeline', 'Lists'].forEach((label, index) => {
      expect(labels[index]).toContain(label)
    })
  })

  it('keeps the consolidated surfaces reachable under Research', async () => {
    setUser('user')
    const wrapper = await mountSidebar(makeRouter())
    const research = wrapper.find('[data-test="nav-research"]')
    expect(research.exists()).toBe(true)
    const html = research.html()
    expect(html).toContain('href="/philadelphia/feed"')
    expect(html).toContain('href="/philadelphia/sheriff-sales"')
    expect(html).toContain('href="/philadelphia/top-plays"')
    expect(html).toContain('href="/philadelphia/buyers"')
    expect(html).toContain('href="/philadelphia/market"')
  })

  it('opens Research when one of its surfaces is the active route', async () => {
    setUser('user')
    const router = makeRouter()
    await router.push({ name: 'buyers', params: { market: 'philadelphia' } })
    const wrapper = await mountSidebar(router)
    expect(wrapper.find('.nav-active').text()).toContain('Cash buyers')
  })
})
