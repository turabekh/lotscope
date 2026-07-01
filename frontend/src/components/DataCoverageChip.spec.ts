import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import DataCoverageChip from '@/components/DataCoverageChip.vue'
import { MARKET_LABELS, useMarketStore } from '@/stores/market'

describe('DataCoverageChip', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders the active market label from the store, not a hardcoded city', () => {
    const wrapper = mount(DataCoverageChip, { global: { plugins: [[Quasar, {}]] } })
    expect(wrapper.text()).toContain(MARKET_LABELS[useMarketStore().active])
    expect(wrapper.text()).toContain('city data')
  })
})
