import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, api, setAuthToken } from '@/lib/api'
import type { RegisterPayload, User } from '@/lib/types'

const TOKEN_KEY = 'lotscope_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<User | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const dialogOpen = ref(false)

  setAuthToken(token.value)

  const isAuthenticated = computed(() => token.value !== null && user.value !== null)

  function persist(value: string | null): void {
    token.value = value
    setAuthToken(value)
    if (value !== null) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await api.login(email, password)
      persist(response.access_token)
      user.value = await api.getMe()
      dialogOpen.value = false
    } catch (cause) {
      persist(null)
      error.value = cause instanceof ApiError ? cause.message : 'Sign in failed.'
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function register(payload: RegisterPayload): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await api.register(payload)
    } catch (cause) {
      error.value = cause instanceof ApiError ? cause.message : 'Registration failed.'
      loading.value = false
      throw cause
    }
    await login(payload.email, payload.password)
  }

  async function restore(): Promise<void> {
    if (token.value === null) return
    try {
      user.value = await api.getMe()
    } catch {
      persist(null)
      user.value = null
    }
  }

  function logout(): void {
    persist(null)
    user.value = null
  }

  function openDialog(): void {
    error.value = null
    dialogOpen.value = true
  }

  return {
    token,
    user,
    loading,
    error,
    dialogOpen,
    isAuthenticated,
    login,
    register,
    restore,
    logout,
    openDialog,
  }
})
