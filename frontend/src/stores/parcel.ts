import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type {
  AssemblageResult,
  AssessmentResult,
  DealResult,
  DeedRestrictionsResponse,
  DistressResult,
  EnvelopeResult,
  OwnerPortfolio,
  ParcelChecklist,
  ParcelDetail,
  SubdivisionResult,
  VerdictResult,
} from '@/lib/types'

export const useParcelStore = defineStore('parcel', () => {
  const detail = ref<ParcelDetail | null>(null)
  const verdict = ref<VerdictResult | null>(null)
  const envelope = ref<EnvelopeResult | null>(null)
  const assemblage = ref<AssemblageResult | null>(null)
  const assemblageLoading = ref(false)
  const distress = ref<DistressResult | null>(null)
  const assessment = ref<AssessmentResult | null>(null)
  const subdivision = ref<SubdivisionResult | null>(null)
  const deal = ref<DealResult | null>(null)
  const dealLoading = ref(false)
  const checklist = ref<ParcelChecklist | null>(null)
  const ownerPortfolio = ref<OwnerPortfolio | null>(null)
  const deedRestrictions = ref<DeedRestrictionsResponse | null>(null)
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
    distress.value = null
    assessment.value = null
    subdivision.value = null
    deal.value = null
    checklist.value = null
    ownerPortfolio.value = null
    deedRestrictions.value = null
    try {
      detail.value = await api.getParcel(parcelNumber)
      verdict.value = await loadVerdict(parcelNumber)
      void loadAssemblage(parcelNumber)
      void loadDistress(parcelNumber)
      void loadAssessment(parcelNumber)
      void loadSubdivision(parcelNumber)
      void loadDeal(parcelNumber)
      void loadChecklist(parcelNumber)
      void loadOwnerPortfolio(parcelNumber)
      void loadDeedRestrictions(parcelNumber)
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

  async function loadDistress(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getDistress(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) distress.value = result
    } catch {
      distress.value = null
    }
  }

  async function loadAssessment(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getAssessment(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) assessment.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) assessment.value = null
    }
  }

  async function loadSubdivision(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getSubdivision(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) subdivision.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) subdivision.value = null
    }
  }

  async function loadDeal(
    parcelNumber: string,
    overrides: { acquisitionPrice?: number | null; targetMargin?: number | null } = {},
  ): Promise<void> {
    dealLoading.value = true
    try {
      const result = await api.getDeal(parcelNumber, overrides)
      if (detail.value?.parcel_number === parcelNumber) deal.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) deal.value = null
    } finally {
      dealLoading.value = false
    }
  }

  async function loadChecklist(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getChecklist(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) checklist.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) checklist.value = null
    }
  }

  async function loadOwnerPortfolio(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getOwnerPortfolio(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) ownerPortfolio.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) ownerPortfolio.value = null
    }
  }

  async function loadDeedRestrictions(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getDeedRestrictions(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) deedRestrictions.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) deedRestrictions.value = null
    }
  }

  function clear(): void {
    detail.value = null
    verdict.value = null
    envelope.value = null
    assemblage.value = null
    distress.value = null
    assessment.value = null
    subdivision.value = null
    deal.value = null
    checklist.value = null
    ownerPortfolio.value = null
    deedRestrictions.value = null
    error.value = null
    errorStatus.value = null
  }

  return {
    detail,
    verdict,
    envelope,
    assemblage,
    assemblageLoading,
    distress,
    assessment,
    subdivision,
    deal,
    dealLoading,
    checklist,
    ownerPortfolio,
    deedRestrictions,
    loading,
    error,
    errorStatus,
    select,
    refreshVerdict,
    loadEnvelope,
    loadAssemblage,
    loadDistress,
    loadAssessment,
    loadSubdivision,
    loadDeal,
    loadChecklist,
    loadOwnerPortfolio,
    loadDeedRestrictions,
    clear,
  }
})
