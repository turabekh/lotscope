import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ApiError: actual.ApiError,
    setAuthToken: vi.fn(),
    api: { login: vi.fn(), register: vi.fn(), getMe: vi.fn(), markOnboarded: vi.fn() },
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

  it('restore drops an invalid token', async () => {
    localStorage.setItem('lotscope_token', 'bad')
    vi.mocked(api.getMe).mockRejectedValue(new Error('unauthorized'))

    const store = useAuthStore()
    await store.restore()

    expect(store.user).toBeNull()
    expect(localStorage.getItem('lotscope_token')).toBeNull()
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
    vi.mocked(api.markOnboarded).mockResolvedValue({ ...user, onboarded_at: '2026-07-11T00:00:00Z' })

    const store = useAuthStore()
    store.user = { ...user }
    await store.markOnboarded()

    expect(api.markOnboarded).toHaveBeenCalledTimes(1)
    expect(store.user?.onboarded_at).toBe('2026-07-11T00:00:00Z')
  })
})
