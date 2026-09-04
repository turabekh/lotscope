import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MarketHealthPage from '@/pages/MarketHealthPage.vue'
import type { User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { market: 'hbg' } }),
}))

const { getMarketHealthMock } = vi.hoisted(() => ({
  getMarketHealthMock: vi.fn(() =>
    Promise.resolve({
      market_code: 'hbg',
      name: 'Harrisburg',
      launch_status: 'pilot',
      coverage_note: 'Harrisburg city pilot — no open sale-price comps.',
      health: { status: 'amber', red: 0, amber: 2, green: 8 },
      datasets: [
        {
          dataset: 'dc_tax_claim',
          cadence: 'seasonal',
          freshness: 'green',
          reason: 'Off-season — next expected in August to September.',
          ingest_status: 'success',
          last_success_at: null,
          last_attempt_at: null,
          row_count: null,
        },
      ],
      coverage: {
        parcel_count: 20000,
        geometry_pct: 100.0,
        verdict_pct: 100.0,
        vacant_count: 1664,
        vacant_with_comp_pct: 0.0,
        computed_at: '2026-07-11T09:30:00Z',
      },
      zoning_standard_count: 12,
      zoning_district_count: 12,
      verdict_versions: [{ verdict_version: 'v8', count: 20000 }],
      recent_jobs: [],
      generated_at: '2026-07-11T12:00:00Z',
    }),
  ),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: { ...actual.api, getOpsMarketHealth: getMarketHealthMock },
  }
})

function adminUser(): User {
  return { id: 1, email: 'a@example.com', role: 'admin' } as User
}

async function mountPage() {
  const wrapper = mount(MarketHealthPage, {
    global: {
      plugins: [[Quasar, {}]],
      stubs: { QPage: { template: '<div><slot /></div>' }, QBtn: true },
    },
  })
  await flushPromises()
  return wrapper
}

describe('MarketHealthPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    getMarketHealthMock.mockClear()
    useAuthStore().user = adminUser()
  })

  it('renders datasets with honest cadence reasons', async () => {
    const wrapper = await mountPage()
    expect(getMarketHealthMock).toHaveBeenCalledWith('hbg')
    expect(wrapper.text()).toContain('dc_tax_claim')
    expect(wrapper.text()).toContain('Off-season — next expected in August to September.')
  })

  it('surfaces the verdict spread', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('v8: 20,000')
  })

  it('blocks non-admins', async () => {
    useAuthStore().user = { id: 2, email: 'b@example.com', role: 'user' } as User
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Administrator access required')
  })
})
