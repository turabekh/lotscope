import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Notify, Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import PipelinePage from '@/pages/PipelinePage.vue'
import type { DealItem, User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const { exportMock } = vi.hoisted(() => ({ exportMock: vi.fn(() => Promise.resolve()) }))

function oneDeal(): DealItem {
  return {
    id: 1,
    parcel_number: '001',
    stage: 'lead',
    note: null,
    target_price: null,
    next_action: null,
    next_action_due: null,
    stage_entered_at: null,
    contact_name: null,
    contact_phone: null,
    contact_email: null,
    address: '1 Main',
    base_zoning_code: null,
    is_vacant: null,
    market_value: null,
    opportunity_score: null,
    max_allowable_offer: null,
    arv: null,
    est_profit: null,
    est_margin: null,
    is_underpriced: null,
    updated_at: '2026-07-11T00:00:00Z',
  }
}

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      getPipeline: vi.fn(() => Promise.resolve({ limit: null, used: 1, deals: [oneDeal()] })),
      exportPipeline: exportMock,
    },
  }
})

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/:market/pipeline', name: 'pipeline', component: PipelinePage },
      { path: '/account', name: 'account', component: { template: '<div />' } },
      { path: '/:market/explore', name: 'explore', component: { template: '<div />' } },
      { path: '/:market/parcel/:id', name: 'parcel', component: { template: '<div />' } },
    ],
  })
}

async function mountPage() {
  const router = makeRouter()
  await router.push('/philadelphia/pipeline')
  await router.isReady()
  const wrapper = mount(PipelinePage, {
    global: {
      plugins: [router, [Quasar, { plugins: { Notify } }]],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('PipelinePage CSV export', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    exportMock.mockClear()
  })

  it('shows a locked upgrade link for free tier', async () => {
    useAuthStore().user = { id: 1, email: 'a@b.co', role: 'user', tier: 'free' } as User
    const wrapper = await mountPage()
    expect(wrapper.find('a.export-btn').exists()).toBe(true)
    expect(wrapper.find('button.export-btn').exists()).toBe(false)
    expect(exportMock).not.toHaveBeenCalled()
  })

  it('exports for a paid tier on click', async () => {
    useAuthStore().user = { id: 1, email: 'a@b.co', role: 'user', tier: 'pro' } as User
    const wrapper = await mountPage()
    const button = wrapper.find('button.export-btn')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    await flushPromises()
    expect(exportMock).toHaveBeenCalledTimes(1)
  })
})
