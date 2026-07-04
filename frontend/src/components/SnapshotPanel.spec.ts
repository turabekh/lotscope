import { flushPromises, mount } from '@vue/test-utils'
import { Quasar } from 'quasar'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SnapshotPanel from '@/components/SnapshotPanel.vue'
import { api } from '@/lib/api'
import type { ParcelSummaryResult } from '@/lib/types'

function makeSummary(parcelNumber: string): ParcelSummaryResult {
  return {
    parcel_number: parcelNumber,
    summary: `Summary for ${parcelNumber}`,
    confidence: 'high',
    is_informational: true,
    sources: [],
    computed_at: '2026-07-05T00:00:00Z',
  } as ParcelSummaryResult
}

describe('SnapshotPanel', () => {
  afterEach(() => vi.restoreAllMocks())

  it('discards a stale slow response when the parcel changed mid-flight', async () => {
    let resolveSlow: (value: ParcelSummaryResult) => void = () => {}
    const spy = vi.spyOn(api, 'getParcelSummary').mockImplementation((parcel: string) => {
      if (parcel === '056152260') {
        return new Promise<ParcelSummaryResult>((resolve) => {
          resolveSlow = resolve
        })
      }
      return Promise.resolve(makeSummary(parcel))
    })

    const wrapper = mount(SnapshotPanel, {
      props: { parcelNumber: '056152260' },
      global: { plugins: [[Quasar, {}]] },
    })

    await wrapper.setProps({ parcelNumber: '056219700' })
    await flushPromises()

    expect(wrapper.text()).toContain('Summary for 056219700')

    resolveSlow(makeSummary('056152260'))
    await flushPromises()

    expect(wrapper.text()).toContain('Summary for 056219700')
    expect(wrapper.text()).not.toContain('Summary for 056152260')
    expect(spy).toHaveBeenCalledTimes(2)
  })
})
