import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { marketGuard, routes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'

function makeRouter(): Router {
  const router = createRouter({ history: createMemoryHistory(), routes })
  router.beforeEach(marketGuard)
  return router
}

function authenticate(): void {
  useAuthStore().token = 'test-token'
}

describe('marketGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('normalizes an unknown market segment to the default market', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/atlantis/leads')
    expect(router.currentRoute.value.name).toBe('leads')
    expect(router.currentRoute.value.params.market).toBe('philadelphia')
    expect(router.currentRoute.value.fullPath).toBe('/philadelphia/leads')
  })

  it('sends an unauthenticated deep-link to login preserving the requested market', async () => {
    const router = makeRouter()
    await router.push('/philadelphia/explore')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/philadelphia/explore')
    expect(useMarketStore().active).toBe('philadelphia')
  })

  it('redirects the bare market root through home to explore', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/philadelphia')
    expect(router.currentRoute.value.name).toBe('explore')
    expect(router.currentRoute.value.fullPath).toBe('/philadelphia/explore')
  })

  it('sets the active market from a valid market segment', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/philadelphia/pipeline')
    expect(router.currentRoute.value.name).toBe('pipeline')
    expect(useMarketStore().active).toBe('philadelphia')
  })

  it('redirects an authenticated visitor from the landing page to their market home', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('explore')
    expect(router.currentRoute.value.fullPath).toBe('/philadelphia/explore')
  })

  it('redirects the retired watchlist path to the Lists "lots" tab', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/philadelphia/watchlist')
    expect(router.currentRoute.value.name).toBe('lists')
    expect(router.currentRoute.value.query.tab).toBe('lots')
  })

  it('redirects the retired saved-searches path to the Lists "searches" tab, preserving query', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/philadelphia/saved-searches?vacant=1')
    expect(router.currentRoute.value.name).toBe('lists')
    expect(router.currentRoute.value.query.tab).toBe('searches')
    expect(router.currentRoute.value.query.vacant).toBe('1')
  })
})
