import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { api } from '@/lib/api'
import HomePage from '@/pages/HomePage.vue'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      getWatchlist: vi.fn(() => Promise.resolve({ limit: null, used: 0, alerts: 0, items: [] })),
      getSavedSearches: vi.fn(() => Promise.resolve({ limit: null, used: 0, searches: [] })),
      getPipeline: vi.fn(() => Promise.resolve({ limit: null, used: 0, deals: [] })),
      getLeads: vi.fn(() => Promise.resolve({ tier: 'free', limit: 8, returned: 0, leads: [] })),
      listUnderwritingProfiles: vi.fn(() => Promise.resolve([])),
      getBuyBoxMatches: vi.fn(() =>
        Promise.resolve({
          market: 'phl',
          total: 0,
          matches: [],
          criteria_applied: ['max_acquisition_price'],
          has_profile: true,
        }),
      ),
    },
  }
})

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/:market/home', name: 'home', component: HomePage },
      { path: '/:market/explore', name: 'explore', component: { template: '<div />' } },
      { path: '/:market/leads', name: 'leads', component: { template: '<div />' } },
      { path: '/:market/pipeline', name: 'pipeline', component: { template: '<div />' } },
      { path: '/:market/lists', name: 'lists', component: { template: '<div />' } },
      { path: '/account', name: 'account', component: { template: '<div />' } },
    ],
  })
}

async function mountHome() {
  const router = makeRouter()
  await router.push('/philadelphia/home')
  await router.isReady()
  const wrapper = mount(HomePage, {
    global: {
      plugins: [router, [Quasar, {}]],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('HomePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the four snapshot cards for the active market', async () => {
    const wrapper = await mountHome()
    const text = wrapper.text()
    expect(text).toContain('What changed')
    expect(text).toContain('Pipeline')
    expect(text).toContain('Top leads')
    expect(text).toContain('Philadelphia')
  })

  it('shows the caught-up empty state when there is nothing new', async () => {
    const wrapper = await mountHome()
    expect(wrapper.text()).toContain("You're all caught up")
  })

  it('shows which way a watched score moved and whether that is good', async () => {
    vi.mocked(api.getWatchlist).mockResolvedValueOnce({
      limit: null,
      used: 2,
      alerts: 2,
      items: [
        {
          parcel_number: 'phl:1',
          address: '2250 KIMBALL ST',
          has_alerts: true,
          changes: [
            {
              code: 'opportunity',
              label: 'Opportunity 54 → 46',
              severity: 'info',
              direction: 'down',
            },
          ],
        },
        {
          parcel_number: 'phl:2',
          address: '4939 CHESTNUT ST',
          has_alerts: true,
          changes: [
            { code: 'distress', label: 'Distress 65 → 75', severity: 'medium', direction: 'up' },
          ],
        },
      ],
    } as never)

    const wrapper = await mountHome()

    const worse = wrapper.find('.meaning-worse')
    const better = wrapper.find('.meaning-better')
    expect(worse.exists()).toBe(true)
    expect(better.exists()).toBe(true)
    expect(wrapper.text()).toContain('Opportunity 54 → 46')
    expect(wrapper.text()).toContain('Distress 65 → 75')
  })

  it('leads with an action rather than a status card', async () => {
    const wrapper = await mountHome()
    expect(wrapper.find('[data-test="next-action-explore"]').exists()).toBe(true)
  })
})
