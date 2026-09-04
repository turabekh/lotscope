import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ApiError: actual.ApiError,
    setAuthToken: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
    setEmailUnverifiedHandler: vi.fn(),
    api: {
      login: vi.fn(),
      register: vi.fn(),
      getMe: vi.fn(),
      markOnboarded: vi.fn(),
      refreshToken: vi.fn(),
    },
  }
})

const user = {
  id: 1,
  email: 'a@b.co',
  full_name: null,
  role: 'user',
  tier: 'free',
  is_active: true,
  subscription_status: null,
  digest_frequency: 'weekly' as const,
  onboarded_at: null,
  created_at: '',
}

const token = { access_token: 'tok', token_type: 'bearer' }

function tokenExpiringIn(seconds: number): string {
  const payload = btoa(JSON.stringify({ sub: '1', exp: Math.floor(Date.now() / 1000) + seconds }))
  return `header.${payload}.signature`
}

const liveToken = () => tokenExpiringIn(60 * 60)
const expiredToken = () => tokenExpiringIn(-60)

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('logs in, persists the token, and loads the user', async () => {
    vi.mocked(api.login).mockResolvedValue(token)
    vi.mocked(api.getMe).mockResolvedValue(user)

    const store = useAuthStore()
    await store.login('a@b.co', 'password1')

    expect(store.isAuthenticated).toBe(true)
    expect(store.user?.email).toBe('a@b.co')
    expect(localStorage.getItem('lotscope_token')).toBe('tok')
  })

  it('logout clears token and user', async () => {
    vi.mocked(api.login).mockResolvedValue(token)
    vi.mocked(api.getMe).mockResolvedValue(user)

    const store = useAuthStore()
    await store.login('a@b.co', 'password1')
    store.logout()

    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('restore loads the user when a token is stored', async () => {
    localStorage.setItem('lotscope_token', 'tok')
    vi.mocked(api.getMe).mockResolvedValue(user)

    const store = useAuthStore()
    await store.restore()

    expect(store.user?.email).toBe('a@b.co')
  })

  it('restore drops the session when the server rejects the token', async () => {
    localStorage.setItem('lotscope_token', liveToken())
    vi.mocked(api.getMe).mockRejectedValue(new ApiError(401, 'unauthorized'))

    const store = useAuthStore()
    await store.restore()

    expect(store.user).toBeNull()
    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('restore keeps the session when the failure is not the token', async () => {
    localStorage.setItem('lotscope_token', liveToken())
    vi.mocked(api.getMe).mockRejectedValue(new Error('network down'))

    const store = useAuthStore()
    await store.restore()

    expect(localStorage.getItem('lotscope_token')).not.toBeNull()
  })

  it('treats an expired token as signed out without asking the server', async () => {
    localStorage.setItem('lotscope_token', expiredToken())

    const store = useAuthStore()
    expect(store.hasLiveToken).toBe(false)

    await store.restore()

    expect(api.getMe).not.toHaveBeenCalled()
    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('does not try to refresh a token that has already expired', async () => {
    localStorage.setItem('lotscope_token', expiredToken())

    const store = useAuthStore()
    await store.refresh()

    expect(api.refreshToken).not.toHaveBeenCalled()
    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('refreshes a token that is close to expiring', async () => {
    localStorage.setItem('lotscope_token', tokenExpiringIn(60))
    vi.mocked(api.refreshToken).mockResolvedValue({
      access_token: liveToken(),
      token_type: 'bearer',
    })

    const store = useAuthStore()
    await store.refreshIfExpiring()

    expect(api.refreshToken).toHaveBeenCalled()
  })

  it('leaves a healthy token alone', async () => {
    localStorage.setItem('lotscope_token', liveToken())

    const store = useAuthStore()
    await store.refreshIfExpiring()

    expect(api.refreshToken).not.toHaveBeenCalled()
  })

  it('ensureRestored fetches the user once across concurrent callers', async () => {
    localStorage.setItem('lotscope_token', 'tok')
    vi.mocked(api.getMe).mockResolvedValue(user)

    const store = useAuthStore()
    await Promise.all([store.ensureRestored(), store.ensureRestored()])
    await store.ensureRestored()

    expect(api.getMe).toHaveBeenCalledTimes(1)
    expect(store.user?.email).toBe('a@b.co')
  })

  it('markOnboarded stamps the user from the server copy', async () => {
    vi.mocked(api.markOnboarded).mockResolvedValue({
      ...user,
      onboarded_at: '2026-07-11T00:00:00Z',
    })

    const store = useAuthStore()
    store.user = { ...user }
    await store.markOnboarded()

    expect(api.markOnboarded).toHaveBeenCalledTimes(1)
    expect(store.user?.onboarded_at).toBe('2026-07-11T00:00:00Z')
  })

  it('signs out on a 401 when the token has expired', async () => {
    localStorage.setItem('lotscope_token', expiredToken())

    const store = useAuthStore()
    await store.handleUnauthorized()

    expect(localStorage.getItem('lotscope_token')).toBeNull()
    expect(api.getMe).not.toHaveBeenCalled()
  })

  it('keeps the session when a 401 came from a forbidden endpoint, not a dead token', async () => {
    localStorage.setItem('lotscope_token', liveToken())
    vi.mocked(api.getMe).mockResolvedValue(user)

    const store = useAuthStore()
    await store.handleUnauthorized()

    expect(localStorage.getItem('lotscope_token')).not.toBeNull()
    expect(store.user).toEqual(user)
  })

  it('signs out when the server rejects a token that has not expired yet', async () => {
    localStorage.setItem('lotscope_token', liveToken())
    vi.mocked(api.getMe).mockRejectedValue(new ApiError(401, 'unauthorized'))

    const store = useAuthStore()
    await store.handleUnauthorized()

    expect(localStorage.getItem('lotscope_token')).toBeNull()
  })

  it('verifies once even if several requests fail at the same time', async () => {
    localStorage.setItem('lotscope_token', liveToken())
    vi.mocked(api.getMe).mockResolvedValue(user)

    const store = useAuthStore()
    await Promise.all([
      store.handleUnauthorized(),
      store.handleUnauthorized(),
      store.handleUnauthorized(),
    ])

    expect(api.getMe).toHaveBeenCalledTimes(1)
  })
})
