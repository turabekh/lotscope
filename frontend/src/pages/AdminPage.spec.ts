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
      label: 'HBG · zoning',
      kind: 'ingest',
      market_code: 'hbg',
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
      id: 'ingest:hbg:zoning',
      label: 'HBG · zoning',
      kind: 'ingest',
      description: 'Ingest the zoning dataset for HBG.',
      market: 'hbg',
      dataset: 'zoning',
      params: [],
      latest_run: null,
    },
    {
      id: 'ingest:hbg:tax_claim',
      label: 'HBG · tax_claim',
      kind: 'ingest',
      description: 'Ingest the tax_claim dataset for HBG.',
      market: 'hbg',
      dataset: 'tax_claim',
      params: [
        { name: 'list_url', label: 'Upset / judicial list CSV URL', type: 'string', required: true },
        { name: 'list_date', label: 'List date', type: 'date', required: true },
      ],
      latest_run: null,
    },
    {
      id: 'recompute:distress',
      label: 'Recompute distress index',
      kind: 'recompute',
      description: 'Recompute the distress index.',
      market: null,
      dataset: null,
      params: [],
      latest_run: latestRun,
    },
  ]
  return {
    ...actual,
    api: {
      ...actual.api,
      getAdminOverview: vi.fn(() =>
        Promise.resolve({
          users_total: 0,
          users_by_tier: {},
          parcels_total: 0,
          parcels_vacant: 0,
          verdicts_total: 0,
          deeds_total: 0,
          saved_searches_total: 0,
          neighborhoods_total: 0,
        }),
      ),
      getAdminDatasets: vi.fn(() => Promise.resolve([])),
      getAdminUsers: vi.fn(() => Promise.resolve({ total: 0, users: [] })),
      getJobCatalog: vi.fn(() => Promise.resolve(catalog)),
      getJobRuns: vi.fn(() => Promise.resolve([latestRun])),
      getFetchSources: vi.fn(() =>
        Promise.resolve([
          {
            label: 'Dauphin repository list (PDF)',
            url: 'https://example.test/repo.pdf',
            description: 'Master repository list.',
          },
        ]),
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

  it('lists catalog jobs grouped for the admin', async () => {
    const wrapper = await mountAdmin()
    expect(wrapper.text()).toContain('HBG · zoning')
    expect(wrapper.text()).toContain('Recompute distress index')
  })

  it('triggers a paramless job directly when Run is clicked', async () => {
    const wrapper = await mountAdmin()
    const target = wrapper.findAll('button').find((button) => button.text() === 'Run')
    expect(target).toBeTruthy()
    await target!.trigger('click')
    await flushPromises()
    expect(runJobMock).toHaveBeenCalledWith('ingest:hbg:zoning', {})
  })

  it('renders the server data puller with known-source shortcuts', async () => {
    const wrapper = await mountAdmin()
    expect(wrapper.text()).toContain('Pull data from the server')
    expect(wrapper.text()).toContain('Dauphin repository list (PDF)')
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
