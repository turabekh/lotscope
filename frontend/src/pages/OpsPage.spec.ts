import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import OpsPage from '@/pages/OpsPage.vue'
import type { User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const pushMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      getOpsFleet: vi.fn(() =>
        Promise.resolve({
          generated_at: '2026-07-11T12:00:00Z',
          git_sha: 'abc1234def',
          markets: [
            {
              market_code: 'phl',
              name: 'Philadelphia',
              launch_status: 'live',
              health: { status: 'red', red: 1, amber: 0, green: 4 },
              coverage: {
                parcel_count: 500000,
                geometry_pct: 98.6,
                verdict_pct: 7.0,
                vacant_count: 36000,
                vacant_with_comp_pct: 93.7,
                computed_at: '2026-07-11T09:30:00Z',
              },
              last_ingest_at: '2026-07-11T04:00:00Z',
              zoning_standard_count: 42,
            },
          ],
        }),
      ),
      runSheriffCoverage: vi.fn(() =>
        Promise.resolve({
          market_code: 'phl',
          total_listings: 1493,
          with_opa: 1488,
          without_opa: 5,
          unique_parcels: 1483,
          reconciled: 1446,
          unreconciled: 37,
          coverage_pct: 97.5,
          sample_unreconciled: ['phl:888888888'],
          checked_at: '2026-07-12T10:00:00Z',
        }),
      ),
    },
  }
})

function adminUser(): User {
  return { id: 1, email: 'a@example.com', role: 'admin' } as User
}

async function mountPage() {
  const wrapper = mount(OpsPage, {
    global: {
      plugins: [[Quasar, {}]],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('OpsPage fleet health', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    pushMock.mockClear()
    useAuthStore().user = adminUser()
  })

  it('renders a fleet row per market with health and coverage', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Philadelphia')
    expect(wrapper.text()).toContain('red')
    expect(wrapper.text()).toContain('93.7%')
    expect(wrapper.text()).toContain('1R / 0A / 4G')
  })

  it('shows the deployed short sha', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('deployed abc1234')
  })

  it('navigates to the market health page on row click', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.fleet-row').trigger('click')
    expect(pushMock).toHaveBeenCalledWith({ name: 'ops-market', params: { market: 'phl' } })
  })

  it('blocks non-admins', async () => {
    useAuthStore().user = { id: 2, email: 'b@example.com', role: 'user' } as User
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Administrator access required')
  })

  it('runs the sheriff-sale coverage check and renders the result', async () => {
    const wrapper = await mountPage()
    const runButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Run coverage check'))
    expect(runButton).toBeDefined()
    await runButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('97.5%')
    expect(wrapper.text()).toContain('1,446 of 1,483 parcels')
    expect(wrapper.text()).toContain('phl:888888888')
  })
})
