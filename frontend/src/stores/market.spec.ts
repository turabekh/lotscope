import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MarketInfo } from '@/lib/types'
import { useMarketStore } from '@/stores/market'

const PHL: MarketInfo = {
  code: 'phl',
  name: 'Philadelphia',
  state: 'PA',
  url_slug: 'philadelphia',
  map_center: [-75.1652, 39.9526],
  map_bounds: null,
  default_zoom: 13,
  launch_status: 'live',
  coverage_note: null,
}

vi.mock('@/lib/api', () => ({
  api: { getMarkets: vi.fn(() => Promise.resolve([PHL])) },
}))

describe('market store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('loads market registry and resolves the active market info by slug', async () => {
    const store = useMarketStore()
    expect(store.activeInfo).toBeNull()
    await store.load()
    expect(store.infos).toHaveLength(1)
    expect(store.activeInfo?.map_center).toEqual([-75.1652, 39.9526])
    expect(store.activeInfo?.default_zoom).toBe(13)
  })
})
