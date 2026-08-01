import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { marketGuard, routes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'

const getMe = vi.fn()

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    api: { ...actual.api, getMe: () => getMe() },
  }
})

function makeRouter(): Router {
  const router = createRouter({ history: createMemoryHistory(), routes })
  router.beforeEach(marketGuard)
  return router
}

function authenticate(): void {
  useAuthStore().token = 'test-token'
}

function tokenExpiringIn(seconds: number): string {
  const payload = btoa(JSON.stringify({ sub: '1', exp: Math.floor(Date.now() / 1000) + seconds }))
  return `header.${payload}.signature`
}

function authenticateWithExpiredToken(): void {
  const auth = useAuthStore()
  auth.token = tokenExpiringIn(-60)
  localStorage.setItem('lotscope_token', auth.token)
}

describe('marketGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
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

  it('redirects the bare market root to the market home dashboard', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/philadelphia')
    expect(router.currentRoute.value.name).toBe('home')
    expect(router.currentRoute.value.fullPath).toBe('/philadelphia/home')
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
    expect(router.currentRoute.value.name).toBe('home')
    expect(router.currentRoute.value.fullPath).toBe('/philadelphia/home')
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

  it('keeps a non-admin off an admin deep-link on a cold load, before the user resolves', async () => {
    authenticate()
    getMe.mockResolvedValue({ id: 1, email: 'a@b.c', tier: 'pro', role: 'user' })
    const router = makeRouter()
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('home')
    expect(getMe).toHaveBeenCalledTimes(1)
  })

  it('admits an admin to an admin deep-link on a cold load', async () => {
    authenticate()
    getMe.mockResolvedValue({ id: 1, email: 'a@b.c', tier: 'pro', role: 'admin' })
    const router = makeRouter()
    await router.push('/admin/ops')
    expect(router.currentRoute.value.name).toBe('ops')
  })

  it('sends an admin deep-link away when the stored token is no longer valid', async () => {
    authenticate()
    getMe.mockRejectedValue(new Error('unauthorized'))
    const router = makeRouter()
    await router.push('/admin')
    expect(router.currentRoute.value.name).not.toBe('admin')
  })

  it('sends an expired session to login instead of into the app', async () => {
    authenticateWithExpiredToken()
    const router = makeRouter()
    await router.push('/philadelphia/pipeline')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/philadelphia/pipeline')
  })

  it('clears the dead token rather than leaving it to fail every request', async () => {
    authenticateWithExpiredToken()
    const router = makeRouter()
    await router.push('/philadelphia/pipeline')
    expect(useAuthStore().token).toBeNull()
    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('lets an expired session see the landing page rather than bouncing it to home', async () => {
    authenticateWithExpiredToken()
    const router = makeRouter()
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('landing')
  })
})
