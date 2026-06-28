import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type {
  AssemblageResult,
  EnvelopeResult,
  ParcelDetail,
  VerdictResult,
} from '@/lib/types'

export const useParcelStore = defineStore('parcel', () => {
  const detail = ref<ParcelDetail | null>(null)
  const verdict = ref<VerdictResult | null>(null)
  const envelope = ref<EnvelopeResult | null>(null)
  const assemblage = ref<AssemblageResult | null>(null)
  const assemblageLoading = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const errorStatus = ref<number | null>(null)

  async function select(parcelNumber: string): Promise<void> {
    loading.value = true
    error.value = null
    errorStatus.value = null
    verdict.value = null
    envelope.value = null
    assemblage.value = null
    try {
      detail.value = await api.getParcel(parcelNumber)
      verdict.value = await loadVerdict(parcelNumber)
      void loadAssemblage(parcelNumber)
    } catch (cause) {
      detail.value = null
      if (cause instanceof ApiError) {
        error.value = cause.message
        errorStatus.value = cause.status
      } else {
        error.value = 'Failed to load parcel.'
        errorStatus.value = null
      }
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

  async function loadEnvelope(): Promise<void> {
    if (detail.value === null) return
    const parcelNumber = detail.value.parcel_number
    if (envelope.value?.parcel_number === parcelNumber) return
    try {
      envelope.value = await api.getEnvelope(parcelNumber)
    } catch {
      envelope.value = null
    }
  }

  async function loadAssemblage(parcelNumber: string): Promise<void> {
    assemblageLoading.value = true
    try {
      const result = await api.getAssemblage(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) assemblage.value = result
    } catch {
      assemblage.value = null
    } finally {
      assemblageLoading.value = false
    }
  }

  function clear(): void {
    detail.value = null
    verdict.value = null
    envelope.value = null
    assemblage.value = null
    error.value = null
    errorStatus.value = null
  }

  return {
    detail,
    verdict,
    envelope,
    assemblage,
    assemblageLoading,
    loading,
    error,
    errorStatus,
    select,
    refreshVerdict,
    loadEnvelope,
    loadAssemblage,
    clear,
  }
})
