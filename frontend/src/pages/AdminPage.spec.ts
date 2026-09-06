import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Notify, Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminPage from '@/pages/AdminPage.vue'
import type { User } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const { runJobMock } = vi.hoisted(() => ({
  runJobMock: vi.fn((jobId: string) =>
    Promise.resolve({
      id: 2,
      job_id: jobId,
      label: 'PHL · zoning',
      kind: 'ingest',
      market_code: 'phl',
      status: 'queued',
      started_at: null,
      finished_at: null,
      result_count: null,
      error: null,
      triggered_by: 1,
      created_at: '2026-07-10T00:00:00Z',
    }),
  ),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  const latestRun = {
    id: 1,
    job_id: 'recompute:distress',
    label: 'Recompute distress index',
    kind: 'recompute',
    market_code: null,
    params: null,
    status: 'success',
    started_at: '2026-07-10T00:00:00Z',
    finished_at: '2026-07-10T00:01:00Z',
    result_count: 10,
    error: null,
    triggered_by: 1,
    created_at: '2026-07-10T00:00:00Z',
  }
  const catalog = [
    {
      id: 'ingest:phl:zoning',
      label: 'PHL · zoning',
      kind: 'ingest',
      description: 'Ingest the zoning dataset for PHL.',
      market: 'phl',
      dataset: 'zoning',
      params: [],
      latest_run: null,
    },
    {
      id: 'ingest:phl:zba',
      label: 'PHL · zba',
      kind: 'ingest',
      description: 'Ingest the zba dataset for PHL.',
      market: 'phl',
      dataset: 'tax_claim',
      params: [
        {
          name: 'list_url',
          label: 'Upset / judicial list CSV URL',
          type: 'string',
          required: true,
        },
        { name: 'list_date', label: 'List date', type: 'date', required: true },
      ],
      latest_run: null,
    },
    {
      id: 'recompute:distress',
      label: 'Recompute distress index',
      kind: 'recompute',
      description: 'Recompute the distress index.',
      dataset: null,
      params: [],
      latest_run: latestRun,
    },
  ]
  return {
    ...actual,
    api: {
      ...actual.api,
      // Typed on purpose: this mock is the only thing standing between a card that
      // reads a field the API stopped returning and a blank /admin in production.
      getAdminOverview: vi.fn(
        (): Promise<import('@/lib/types').AdminOverview> =>
          Promise.resolve({
            users_total: 3,
            users_by_tier: {},
            parcels_total: 4,
            parcels_vacant: 5,
            screened_total: 6,
            deeds_total: 7,
            neighborhoods_total: 8,
          }),
      ),
      getAdminDatasets: vi.fn(() => Promise.resolve([])),
      getAdminUsers: vi.fn(() => Promise.resolve({ total: 0, users: [] })),
      getJobCatalog: vi.fn(() => Promise.resolve(catalog)),
      getJobRuns: vi.fn(() => Promise.resolve([latestRun])),
      getAnalystSpend: vi.fn(() =>
        Promise.resolve({
          day: '2026-09-06',
          spend_usd: '41.00',
          global_ceiling_usd: '50.00',
          fraction: 0.82,
          default_ceiling_usd: '3.00',
          default_run_ceiling: 40,
          users: [
            {
              user_id: 7,
              email: 'heavy@example.com',
              chat_usd: '3.20',
              job_usd: '37.80',
              total_usd: '41.00',
              runs: 12,
              input_tokens: 900000,
              output_tokens: 40000,
              ceiling_usd: '3.00',
              run_ceiling: 40,
              over_ceiling: true,
            },
          ],
        }),
      ),
      runJob: runJobMock,
    },
  }
})

function adminUser(): User {
  return { id: 1, email: 'a@example.com', role: 'admin' } as User
}

async function mountAdmin() {
  const wrapper = mount(AdminPage, {
    global: {
      plugins: [[Quasar, { plugins: { Notify } }]],
      stubs: { QPage: { template: '<div><slot /></div>' } },
    },
  })
  await flushPromises()
  return wrapper
}

describe('AdminPage jobs console', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    runJobMock.mockClear()
    useAuthStore().user = adminUser()
  })

  it('renders every overview card with a real number', async () => {
    // A card for a field the API no longer returns threw on `undefined.toLocaleString()`
    // and took the whole admin screen down. Every card must carry a value.
    const wrapper = await mountAdmin()
    const values = wrapper.findAll('.stat-value').map((node) => node.text())
    expect(values.length).toBeGreaterThan(0)
    expect(values).not.toContain('')
    for (const value of values) expect(value).toMatch(/^[\d,]+$/)
  })

  it('lists catalog jobs grouped for the admin', async () => {
    const wrapper = await mountAdmin()
    expect(wrapper.text()).toContain('PHL · zoning')
    expect(wrapper.text()).toContain('Recompute distress index')
  })

  it('triggers a paramless job directly when Run is clicked', async () => {
    const wrapper = await mountAdmin()
    const target = wrapper.findAll('button').find((button) => button.text() === 'Run')
    expect(target).toBeTruthy()
    await target!.trigger('click')
    await flushPromises()
    expect(runJobMock).toHaveBeenCalledWith('ingest:phl:zoning', {})
  })

  it('renders the server data puller', async () => {
    const wrapper = await mountAdmin()
    expect(wrapper.text()).toContain('Pull data from the server')
  })

  it('opens a param dialog for a job with parameters', async () => {
    const wrapper = await mountAdmin()
    const runWithParams = wrapper.findAll('button').find((button) => button.text() === 'Run…')
    expect(runWithParams).toBeTruthy()
    await runWithParams!.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Upset / judicial list CSV URL')
    expect(runJobMock).not.toHaveBeenCalled()
  })
})

describe('AdminPage analyst spend', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useAuthStore().user = adminUser()
  })

  it("shows today's spend against the global ceiling", async () => {
    const wrapper = await mountAdmin()
    expect(wrapper.get('[data-test="spend-total"]').text()).toBe('$41.00 of $50.00')
    expect(wrapper.get('[data-test="spend-pct"]').text()).toBe('82%')
  })

  it('names the user who spent it and separates chat from jobs', async () => {
    const wrapper = await mountAdmin()
    const row = wrapper.get('[data-test="spend-row"]')
    expect(row.text()).toContain('heavy@example.com')
    // Chat is what the ceiling reads; the total is what the invoice reads.
    expect(row.text()).toContain('$3.20')
    expect(row.text()).toContain('$37.80')
    expect(row.text()).toContain('$41.00')
    expect(row.text()).toContain('at ceiling')
  })
})
