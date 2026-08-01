import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Quasar } from 'quasar'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import FirstSteps from '@/components/FirstSteps.vue'
import { api } from '@/lib/api'
import { routes } from '@/router'
import { useFirstStepsStore } from '@/stores/firstSteps'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

async function mountSteps() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(FirstSteps, { global: { plugins: [router, [Quasar, {}]] } })
  await router.isReady()
  await flushPromises()
  return wrapper
}

function stubStores(): void {
  vi.spyOn(useWatchlistStore(), 'ensureLoaded').mockResolvedValue(undefined)
  vi.spyOn(useSavedSearchesStore(), 'ensureLoaded').mockResolvedValue(undefined)
}

describe('FirstSteps', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders every step as a link the router can actually resolve', async () => {
    stubStores()
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])
    const wrapper = await mountSteps()

    const links = wrapper.findAll('a.step')
    expect(links).toHaveLength(4)
    for (const link of links) {
      const href = link.attributes('href')
      expect(href).toBeTruthy()
      expect(href).not.toContain('undefined')
    }
  })

  it('links assumptions to the unscoped account route', async () => {
    stubStores()
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])
    const wrapper = await mountSteps()
    expect(wrapper.find('[data-test="first-step-assumptions"]').attributes('href')).toBe('/account')
  })

  it('reports progress out of the total', async () => {
    stubStores()
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])
    const wrapper = await mountSteps()
    expect(wrapper.find('[data-test="first-steps-count"]').text()).toBe('0 of 4')
  })

  it('disappears once every step is done', async () => {
    stubStores()
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([
      { id: 1, name: 'Mine', is_default: true, assumptions: { target_margin: 0.2 }, buy_box: {} },
    ] as Awaited<ReturnType<typeof api.listUnderwritingProfiles>>)
    const watchlist = useWatchlistStore()
    const savedSearches = useSavedSearchesStore()
    watchlist.items = [{ parcel_number: 'phl:1' }] as typeof watchlist.items
    savedSearches.searches = [
      { id: 1, name: 'x', alerts_enabled: true },
    ] as typeof savedSearches.searches
    localStorage.setItem('lotscope.firstSteps.verdictSeen', 'true')

    const wrapper = await mountSteps()
    expect(wrapper.find('[data-test="first-steps"]').exists()).toBe(false)
  })

  it('collapses to a single prompt once most of the setup is done', async () => {
    stubStores()
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([
      { id: 1, name: 'Mine', is_default: true, assumptions: { margin: 0.2 }, buy_box: {} },
    ] as never)
    useFirstStepsStore().markVerdictSeen()

    const wrapper = await mountSteps()

    const toggle = wrapper.find('[data-test="first-steps-toggle"]')
    expect(toggle.exists()).toBe(true)
    expect(toggle.text()).toContain('Finish setup')
  })

  it('keeps every step in view while the user is still new', async () => {
    stubStores()
    vi.spyOn(api, 'listUnderwritingProfiles').mockResolvedValue([])

    const wrapper = await mountSteps()

    expect(wrapper.find('[data-test="first-steps-toggle"]').exists()).toBe(false)
  })
})
