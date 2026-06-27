import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { ParcelDetail, VerdictResult } from '@/lib/types'

export const useParcelStore = defineStore('parcel', () => {
  const detail = ref<ParcelDetail | null>(null)
  const verdict = ref<VerdictResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function select(parcelNumber: string): Promise<void> {
    loading.value = true
    error.value = null
    verdict.value = null
    try {
      detail.value = await api.getParcel(parcelNumber)
      verdict.value = await loadVerdict(parcelNumber)
    } catch (cause) {
      detail.value = null
      error.value = cause instanceof Error ? cause.message : 'Failed to load parcel.'
    } finally {
      loading.value = false
    }
  }

  async function loadVerdict(parcelNumber: string): Promise<VerdictResult | null> {
    try {
      return await api.getVerdict(parcelNumber)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        return await api.refreshVerdict(parcelNumber)
      }
      throw cause
    }
  }

  async function refreshVerdict(): Promise<void> {
    if (detail.value === null) return
    verdict.value = await api.refreshVerdict(detail.value.parcel_number)
  }

  function clear(): void {
    detail.value = null
    verdict.value = null
    error.value = null
  }

  return { detail, verdict, loading, error, select, refreshVerdict, clear }
})
