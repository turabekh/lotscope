import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import HistoricPanel from '@/components/HistoricPanel.vue'
import type { HistoricResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function historic(overrides: Partial<HistoricResult> = {}): HistoricResult {
  return {
    parcel_number: 'phl:000000001',
    evaluated: true,
    in_historic_district: false,
    district_name: null,
    designated_date: null,
    note: null,
    sources: [],
    computed_at: '2026-08-11T00:00:00Z',
    ...overrides,
  } as HistoricResult
}

function render(value: HistoricResult | null) {
  setActivePinia(createPinia())
  const store = useParcelStore()
  store.historic = value
  return mount(HistoricPanel, { global: { plugins: [Quasar] } })
}

describe('HistoricPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('affirms the negative when the lot was checked and is clear', () => {
    const wrapper = render(historic())

    expect(wrapper.text()).toContain('Not in a designated historic district')
    expect(wrapper.text()).toContain('Not designated')
  })

  it('does not call a checked-and-clear lot unchecked', () => {
    const wrapper = render(historic())

    expect(wrapper.text()).not.toContain('could not be checked')
    expect(wrapper.text()).not.toContain('Review required')
  })

  it('distinguishes no-data from checked-and-clear', () => {
    const wrapper = render(historic({ evaluated: false }))

    expect(wrapper.text()).toContain('could not be checked')
    expect(wrapper.text()).toContain('a gap in what we hold')
    expect(wrapper.text()).not.toContain('Not in a designated historic district')
  })

  it('still reports a designated district', () => {
    const wrapper = render(
      historic({
        in_historic_district: true,
        district_name: 'Rittenhouse Fitler Historic District',
        designated_date: '1995-06-01',
        note: 'Commission review applies.',
      }),
    )

    expect(wrapper.text()).toContain('Review required')
    expect(wrapper.text()).toContain('Rittenhouse Fitler Historic District')
    expect(wrapper.text()).toContain('Commission review applies.')
  })

  it('renders nothing when historic data is absent', () => {
    const wrapper = render(null)

    expect(wrapper.text()).toBe('')
  })
})
