import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { BuyBoxRecord } from '@/lib/types'
import { api } from '@/lib/api'
import { useFirstStepsStore } from '@/stores/firstSteps'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

function stubStores(): void {
  const watchlist = useWatchlistStore()
  const savedSearches = useSavedSearchesStore()
  vi.spyOn(watchlist, 'ensureLoaded').mockResolvedValue(undefined)
  vi.spyOn(savedSearches, 'ensureLoaded').mockResolvedValue(undefined)
}

describe('firstSteps', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('starts with nothing done', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({ assumptions: {} } as BuyBoxRecord)
    const store = useFirstStepsStore()
    await store.refresh()
    expect(store.completed).toBe(0)
    expect(store.allDone).toBe(false)
    expect(store.steps.map((s) => s.code)).toEqual(['verdict', 'assumptions', 'save', 'alert'])
  })

  it('remembers a seen verdict across sessions', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({ assumptions: {} } as BuyBoxRecord)
    useFirstStepsStore().markVerdictSeen()

    setActivePinia(createPinia())
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({ assumptions: {} } as BuyBoxRecord)
    const reloaded = useFirstStepsStore()
    await reloaded.refresh()
    expect(reloaded.steps[0]!.done).toBe(true)
  })

  it('counts assumptions only when a profile actually carries them', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({ assumptions: {} } as BuyBoxRecord)
    const store = useFirstStepsStore()
    await store.refresh()
    expect(store.assumptionsSet).toBe(false)
  })

  it('marks assumptions done when a profile carries them', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({
      assumptions: { target_margin: 0.2 },
    } as unknown as BuyBoxRecord)
    const store = useFirstStepsStore()
    await store.refresh()
    expect(store.assumptionsSet).toBe(true)
  })

  it('does not claim progress when the profile call fails', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockRejectedValue(new Error('down'))
    const store = useFirstStepsStore()
    await store.refresh()
    expect(store.assumptionsSet).toBe(false)
    expect(store.resolved).toBe(true)
  })

  it('reads saved lots and alerts from their own stores', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({ assumptions: {} } as BuyBoxRecord)
    const watchlist = useWatchlistStore()
    const savedSearches = useSavedSearchesStore()
    watchlist.items = [{ parcel_number: 'phl:1' }] as typeof watchlist.items
    savedSearches.searches = [
      { id: 1, name: 'x', alerts_enabled: true },
    ] as typeof savedSearches.searches

    const store = useFirstStepsStore()
    await store.refresh()
    expect(store.steps[2]!.done).toBe(true)
    expect(store.steps[3]!.done).toBe(true)
    expect(store.completed).toBe(2)
  })

  it('does not count a saved search whose alerts are off', async () => {
    stubStores()
    vi.spyOn(api, 'getBuyBox').mockResolvedValue({ assumptions: {} } as BuyBoxRecord)
    const savedSearches = useSavedSearchesStore()
    savedSearches.searches = [
      { id: 1, name: 'x', alerts_enabled: false },
    ] as typeof savedSearches.searches

    const store = useFirstStepsStore()
    await store.refresh()
    expect(store.steps[3]!.done).toBe(false)
  })
})
