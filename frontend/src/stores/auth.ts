import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  ApiError,
  api,
  setAuthToken,
  setEmailUnverifiedHandler,
  setUnauthorizedHandler,
} from '@/lib/api'
import { isTokenExpired, millisecondsUntilRefresh, shouldRefreshToken } from '@/lib/session'
import type { RegisterPayload, SignerProfile, Usage, User } from '@/lib/types'
import { useAreaSearchStore } from '@/stores/areaSearch'
import { usePipelineStore } from '@/stores/pipeline'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const TOKEN_KEY = 'lotscope_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const pendingVerificationEmail = ref<string | null>(null)
  const emailUnverified = ref(false)
  const user = ref<User | null>(null)
  const usage = ref<Usage | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  setAuthToken(token.value)
  setUnauthorizedHandler(() => void handleUnauthorized())
  setEmailUnverifiedHandler(() => {
    emailUnverified.value = true
  })

  const hasLiveToken = computed(() => token.value !== null && !isTokenExpired(token.value))
  const isAuthenticated = computed(() => hasLiveToken.value && user.value !== null)

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
      usage.value = null
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
      pendingVerificationEmail.value = payload.email
    } catch (cause) {
      error.value = cause instanceof ApiError ? cause.message : 'Registration failed.'
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function verifyEmail(verificationToken: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await api.verifyEmail(verificationToken)
      persist(response.access_token)
      pendingVerificationEmail.value = null
      emailUnverified.value = false
      await restore()
    } catch (cause) {
      error.value =
        cause instanceof ApiError ? cause.message : 'This link is invalid or has expired.'
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function resendVerification(email: string): Promise<void> {
    await api.resendVerification(email)
  }

  async function restore(): Promise<void> {
    if (token.value === null) return
    if (isTokenExpired(token.value)) {
      endSession()
      return
    }
    try {
      user.value = await api.getMe()
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) endSession()
    }
  }

  let restoreOnce: Promise<void> | null = null

  async function ensureRestored(): Promise<void> {
    if (restoreOnce === null) restoreOnce = restore()
    return restoreOnce
  }

  async function refresh(): Promise<void> {
    if (token.value === null) return
    if (isTokenExpired(token.value)) {
      endSession()
      return
    }
    try {
      const response = await api.refreshToken()
      persist(response.access_token)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) endSession()
    }
  }

  async function refreshIfExpiring(): Promise<void> {
    if (token.value === null) return
    if (isTokenExpired(token.value)) {
      endSession()
      return
    }
    if (shouldRefreshToken(token.value)) await refresh()
  }

  function millisecondsUntilNextRefresh(): number | null {
    return millisecondsUntilRefresh(token.value)
  }

  async function refreshUser(): Promise<void> {
    if (token.value === null) return
    try {
      user.value = await api.getMe()
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        persist(null)
        user.value = null
      }
    }
  }

  async function setDigest(frequency: 'off' | 'weekly' | 'daily'): Promise<void> {
    user.value = await api.setDigestPreference(frequency)
  }

  async function setSigner(payload: SignerProfile): Promise<void> {
    user.value = await api.updateSigner(payload)
  }

  async function markOnboarded(): Promise<void> {
    user.value = await api.markOnboarded()
  }

  async function fetchUsage(): Promise<void> {
    if (token.value === null) return
    try {
      usage.value = await api.getUsage()
    } catch {
      usage.value = null
    }
  }

  let verifyingSession = false

  async function handleUnauthorized(): Promise<void> {
    if (token.value === null) return
    if (isTokenExpired(token.value)) {
      endSession()
      return
    }
    if (verifyingSession) return
    verifyingSession = true
    try {
      user.value = await api.getMe()
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) endSession()
    } finally {
      verifyingSession = false
    }
  }

  function endSession(): void {
    if (token.value === null && user.value === null) return
    logout()
  }

  function logout(): void {
    persist(null)
    user.value = null
    usage.value = null
    useWatchlistStore().reset()
    usePipelineStore().reset()
    useSavedSearchesStore().reset()
    useAreaSearchStore().reset()
  }

  return {
    token,
    user,
    usage,
    loading,
    error,
    isAuthenticated,
    hasLiveToken,
    login,
    register,
    verifyEmail,
    resendVerification,
    pendingVerificationEmail,
    emailUnverified,
    restore,
    ensureRestored,
    refresh,
    refreshIfExpiring,
    millisecondsUntilNextRefresh,
    endSession,
    handleUnauthorized,
    refreshUser,
    setDigest,
    setSigner,
    markOnboarded,
    fetchUsage,
    logout,
  }
})
