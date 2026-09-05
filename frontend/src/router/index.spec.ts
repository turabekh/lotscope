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
    await router.push('/deals')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/deals')
  })

  it('opens the Analyst at the root for a signed-in buyer', async () => {
    authenticate()
    const router = makeRouter()
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('analyst')
  })

  it('lands a link to a page Phase 3 deleted on the Analyst rather than a blank 404', async () => {
    authenticate()
    const router = makeRouter()
    for (const gone of ['/explore', '/feed', '/lists', '/top-plays', '/market', '/sheriff-sales']) {
      await router.push(gone)
      expect(router.currentRoute.value.name).toBe('analyst')
    }
  })

  it('keeps a non-admin off an admin deep-link on a cold load, before the user resolves', async () => {
    authenticate()
    getMe.mockResolvedValue({ id: 1, email: 'a@b.c', tier: 'pro', role: 'user' })
    const router = makeRouter()
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('analyst')
    expect(getMe).toHaveBeenCalledTimes(1)
  })

  it('admits an admin to an admin deep-link on a cold load', async () => {
    authenticate()
    getMe.mockResolvedValue({ id: 1, email: 'a@b.c', tier: 'pro', role: 'admin' })
    const router = makeRouter()
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('admin')
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
    await router.push('/deals')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/deals')
  })

  it('clears the dead token rather than leaving it to fail every request', async () => {
    authenticateWithExpiredToken()
    const router = makeRouter()
    await router.push('/deals')
    expect(useAuthStore().token).toBeNull()
    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('lets a signed-out visitor read the welcome page', async () => {
    const router = makeRouter()
    await router.push('/welcome')
    expect(router.currentRoute.value.name).toBe('welcome')
  })
})
