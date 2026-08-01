import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it } from 'vitest'

import NextAction from '@/components/NextAction.vue'
import type { LeadItem } from '@/lib/types'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const lead = {
  parcel_number: 'phl:1',
  address: '616 E INDIANA AVE',
  owner: null,
  base_zoning_code: 'RSA-5',
  is_vacant: true,
  market_value: 100000,
  total_due: null,
  in_sheriff_sale: null,
  score: 80,
  top_factors: ['Tired landlord'],
  deal_score: null,
  max_allowable_offer: null,
  is_underpriced: null,
} as LeadItem

function mountAction(topLead: LeadItem | null = null) {
  return mount(NextAction, {
    props: { topLead },
    global: {
      plugins: [[Quasar, {}]],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
}

describe('NextAction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('sends a new user to the map when there is nothing waiting', () => {
    const wrapper = mountAction()
    expect(wrapper.find('[data-test="next-action-explore"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Find your next lot')
  })

  it('offers the strongest lead when nothing has changed', () => {
    const wrapper = mountAction(lead)
    expect(wrapper.find('[data-test="next-action-lead"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('616 E INDIANA AVE')
    expect(wrapper.text()).toContain('Tired landlord')
  })

  it('prefers changed saved lots over a lead', () => {
    const watchlist = useWatchlistStore()
    watchlist.items = [{ parcel_number: 'phl:2', has_alerts: true }] as never

    const wrapper = mountAction(lead)
    expect(wrapper.find('[data-test="next-action-alerts"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('1 saved lot has changed')
  })

  it('prefers new saved-search matches over everything else', () => {
    const watchlist = useWatchlistStore()
    watchlist.items = [{ parcel_number: 'phl:2', has_alerts: true }] as never
    const searches = useSavedSearchesStore()
    searches.searches = [{ id: 1, name: 'South Philly', new_count: 12 }] as never

    const wrapper = mountAction(lead)
    expect(wrapper.find('[data-test="next-action-matches"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('12 new lots match')
  })

  it('counts a single match in the singular', () => {
    const searches = useSavedSearchesStore()
    searches.searches = [{ id: 1, name: 'South Philly', new_count: 1 }] as never

    expect(mountAction().text()).toContain('1 new lot matches')
  })
})
