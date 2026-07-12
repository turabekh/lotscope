import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import BuyersPage from '@/pages/BuyersPage.vue'
import type { BuyerRoster, User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const { getBuyersMock } = vi.hoisted(() => ({ getBuyersMock: vi.fn() }))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: { ...actual.api, getBuyers: getBuyersMock, downloadBuyersCsv: vi.fn() },
  }
})

function roster(over: Partial<BuyerRoster> = {}): BuyerRoster {
  return {
    market_code: 'phl',
    available: true,
    note: null,
    total: 1,
    returned: 1,
    buyers: [
      {
        buyer_key: 'THEDOOR LLC',
        display_name: 'THEDOOR LLC',
        purchases_window: 10,
        lot_purchases_window: 8,
        last_purchase_at: '2026-05-01',
        median_price: 50000,
        total_consideration: 400000,
        mailing_address: '1 PO BOX',
      },
    ],
    ...over,
  }
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/:market/buyers', name: 'buyers', component: { template: '<div />' } },
      { path: '/:market/buyers/:buyerKey', name: 'buyer-profile', component: { template: '<div />' } },
      { path: '/account', name: 'account', component: { template: '<div />' } },
    ],
  })
}

async function mountPage(tier: string, r: BuyerRoster = roster()) {
  getBuyersMock.mockResolvedValue(r)
  useAuthStore().user = { id: 1, email: 'a@example.com', role: 'user', tier } as User
  const router = makeRouter()
  await router.push('/philadelphia/buyers')
  await router.isReady()
  const wrapper = mount(BuyersPage, {
    global: {
      plugins: [[Quasar, {}], router],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('BuyersPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    getBuyersMock.mockReset()
  })

  it('gates non-investor tiers with an upgrade prompt', async () => {
    const wrapper = await mountPage('pro')
    expect(wrapper.text()).toContain('Investor feature')
    expect(getBuyersMock).not.toHaveBeenCalled()
  })

  it('renders the roster for investor tier', async () => {
    const wrapper = await mountPage('investor')
    expect(getBuyersMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('THEDOOR LLC')
    expect(wrapper.text()).toContain('1 active buyers')
  })

  it('shows the unavailable state when the market is gated', async () => {
    const wrapper = await mountPage(
      'investor',
      roster({ available: false, note: 'Buyer identities are not available for this market.', total: 0, buyers: [] }),
    )
    expect(wrapper.text()).toContain('not available for this market')
  })

  it('shows an empty state when no buyers are loaded', async () => {
    const wrapper = await mountPage('investor', roster({ total: 0, buyers: [] }))
    expect(wrapper.text()).toContain('No active lot buyers loaded')
  })
})
