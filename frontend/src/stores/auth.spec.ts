import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ApiError: actual.ApiError,
    setAuthToken: vi.fn(),
    api: { login: vi.fn(), register: vi.fn(), getMe: vi.fn() },
  }
})

const user = {
  id: 1,
  email: 'a@b.co',
  full_name: null,
  role: 'user',
  tier: 'free',
  is_active: true,
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
})
