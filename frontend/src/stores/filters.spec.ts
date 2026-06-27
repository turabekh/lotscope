import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useFiltersStore } from '@/stores/filters'

describe('filters store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('toggles a use class on and off', () => {
    const store = useFiltersStore()
    store.toggleClass('R')
    expect(store.useClasses).toEqual(['R'])
    store.toggleClass('C')
    expect(store.useClasses).toEqual(['R', 'C'])
    store.toggleClass('R')
    expect(store.useClasses).toEqual(['C'])
  })

  it('counts active filter groups and resets', () => {
    const store = useFiltersStore()
    expect(store.activeCount).toBe(0)
    store.vacantOnly = true
    store.toggleClass('I')
    expect(store.activeCount).toBe(2)
    store.reset()
    expect(store.activeCount).toBe(0)
    expect(store.vacantOnly).toBe(false)
    expect(store.useClasses).toEqual([])
  })
})
