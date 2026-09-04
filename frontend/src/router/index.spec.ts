import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { authGuard, routes } from '@/router'
import { useAuthStore } from '@/stores/auth'

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
  router.beforeEach(authGuard)
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

describe('authGuard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('sends an unauthenticated deep-link to login preserving where it was headed', async () => {
    const router = makeRouter()
    await router.push('/explore')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/explore')
  })

  it('redirects an authenticated visitor from the landing page to their market home', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('home')
    expect(router.currentRoute.value.fullPath).toBe('/home')
  })

  it('redirects the retired watchlist path to the Lists "lots" tab', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/watchlist')
    expect(router.currentRoute.value.name).toBe('lists')
    expect(router.currentRoute.value.query.tab).toBe('lots')
  })

  it('redirects the retired saved-searches path to the Lists "searches" tab, preserving query', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/saved-searches?vacant=1')
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
    await router.push('/pipeline')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/pipeline')
  })

  it('clears the dead token rather than leaving it to fail every request', async () => {
    authenticateWithExpiredToken()
    const router = makeRouter()
    await router.push('/pipeline')
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
