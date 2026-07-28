import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import CorrectionStatus from '@/components/CorrectionStatus.vue'
import { api } from '@/lib/api'
import { routes } from '@/router'
import type { CorrectionRecord } from '@/lib/types'

function record(overrides: Partial<CorrectionRecord> = {}): CorrectionRecord {
  return {
    id: 1,
    parcel_number: 'phl:1',
    market_code: 'phl',
    section: 'buildability',
    field_name: 'by_right_units',
    description: 'The district here is RSA-3.',
    status: 'open',
    resolution: null,
    resolved_at: null,
    created_at: '2026-07-28T00:00:00Z',
    ...overrides,
  }
}

async function mountStatus() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(CorrectionStatus, { global: { plugins: [router, [Quasar, {}]] } })
  await router.isReady()
  await flushPromises()
  return wrapper
}

describe('CorrectionStatus', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('invites a first report when there are none', async () => {
    vi.spyOn(api, 'getOwnCorrections').mockResolvedValue([])
    expect((await mountStatus()).text()).toContain('have not reported any incorrect data')
  })

  it('shows a plain-language status rather than the raw state', async () => {
    vi.spyOn(api, 'getOwnCorrections').mockResolvedValue([record({ status: 'triaged' })])
    const text = (await mountStatus()).text()
    expect(text).toContain('Being reviewed')
    expect(text).not.toContain('triaged')
  })

  it('does not imply a change was made when a report was rejected', async () => {
    vi.spyOn(api, 'getOwnCorrections').mockResolvedValue([
      record({ status: 'rejected', resolution: 'Zoning confirmed as RSA-5.' }),
    ])
    const text = (await mountStatus()).text()
    expect(text).toContain('Reviewed, no change')
    expect(text).toContain('Zoning confirmed as RSA-5.')
  })

  it('states a load failure does not affect reports already sent', async () => {
    vi.spyOn(api, 'getOwnCorrections').mockRejectedValue(new Error('down'))
    const wrapper = await mountStatus()
    expect(wrapper.find('[data-test="correction-status-failed"]').text()).toContain(
      'does not affect any report you have already sent',
    )
  })
})
