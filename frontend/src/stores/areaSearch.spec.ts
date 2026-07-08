import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAreaSearchStore } from '@/stores/areaSearch'

describe('areaSearch store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('counts each active buy-box filter group', () => {
    const store = useAreaSearchStore()
    expect(store.activeCount).toBe(0)

    store.minDistress = 50
    store.sheriffSaleOnly = true
    store.byRightOnly = true
    expect(store.activeCount).toBe(3)
  })

  it('counts a value range as a single group', () => {
    const store = useAreaSearchStore()
    store.minValue = 100_000
    expect(store.activeCount).toBe(1)
    store.maxValue = 500_000
    expect(store.activeCount).toBe(1)
    store.minLotArea = 1_000
    expect(store.activeCount).toBe(2)
  })

  it('resets to zero', () => {
    const store = useAreaSearchStore()
    store.minScore = 60
    store.delinquentOnly = true
    store.underpricedOnly = true
    expect(store.activeCount).toBe(3)
    store.reset()
    expect(store.activeCount).toBe(0)
  })
})
