import { flushPromises, mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { afterEach, describe, expect, it, vi } from 'vitest'

import VarianceOutlookLine from '@/components/VarianceOutlookLine.vue'
import { api } from '@/lib/api'
import type { VarianceOutlook } from '@/lib/types'

function makeOutlook(overrides: Partial<VarianceOutlook>): VarianceOutlook {
  return {
    parcel_number: '000000001',
    district: 'RSA5',
    population_label: 'all ZBA appeals for RSA5 parcels',
    window_months: 36,
    decided: 40,
    granted: 34,
    grant_rate: 0.85,
    local_scope: null,
    local_decided: null,
    local_grant_rate: null,
    reason: null,
    sources: [],
    computed_at: '2026-07-05T00:00:00Z',
    ...overrides,
  }
}

describe('VarianceOutlookLine', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders the district grant rate', async () => {
    vi.spyOn(api, 'getVarianceOutlook').mockResolvedValue(makeOutlook({}))
    const wrapper = mount(VarianceOutlookLine, {
      props: { parcelNumber: '000000001' },
      global: { plugins: [[Quasar, {}]] },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('85%')
    expect(wrapper.text()).toContain('RSA5')
  })

  it('shows the reason when the sample is too thin', async () => {
    vi.spyOn(api, 'getVarianceOutlook').mockResolvedValue(
      makeOutlook({ grant_rate: null, decided: 3, granted: 2, reason: 'too few to estimate' }),
    )
    const wrapper = mount(VarianceOutlookLine, {
      props: { parcelNumber: '000000001' },
      global: { plugins: [[Quasar, {}]] },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('too few to estimate')
    expect(wrapper.text()).not.toContain('%')
  })
})
