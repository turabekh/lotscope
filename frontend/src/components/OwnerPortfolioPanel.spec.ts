import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import OwnerPortfolioPanel from '@/components/OwnerPortfolioPanel.vue'
import type { OwnerPortfolio } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

function mountPanel(portfolio: Partial<OwnerPortfolio> | null) {
  const store = useParcelStore()
  store.ownerPortfolio =
    portfolio === null
      ? null
      : ({
          owner: 'TRS OF THE GEN ASSEM',
          total_count: 1,
          vacant_count: 0,
          total_market_value: 100000,
          parcels: [],
          ...portfolio,
        } as OwnerPortfolio)
  return mount(OwnerPortfolioPanel, { global: { plugins: [[Quasar, {}]] } })
}

describe('OwnerPortfolioPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('states a sole holding rather than rendering nothing', () => {
    const wrapper = mountPanel({ total_count: 1 })
    expect(wrapper.find('[data-test="owner-sole-holding"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('only Philadelphia parcel recorded to this owner')
    expect(wrapper.text()).toContain('TRS OF THE GEN ASSEM')
  })

  it('lists the portfolio when the owner holds more than one parcel', () => {
    const wrapper = mountPanel({
      total_count: 3,
      parcels: [
        {
          parcel_number: 'phl:2',
          address: '1 MAIN ST',
          base_zoning_code: 'RSA-5',
          is_vacant: true,
          market_value: 50000,
          opportunity_score: 70,
        },
      ] as never,
    })
    expect(wrapper.find('[data-test="owner-sole-holding"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('1 MAIN ST')
  })

  it('renders nothing at all only when no portfolio was returned', () => {
    expect(mountPanel(null).text()).toBe('')
  })
})
