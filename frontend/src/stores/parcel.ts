import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type {
  DealOverrides,
  UnderwritingAnalysis,
  AssemblageResult,
  DealResult,
  DeedRestrictionsResponse,
  DistressResult,
  NextSheriffSale,
  EnvelopeResult,
  HistoricResult,
  OwnerPortfolio,
  ParcelChecklist,
  ParcelDetail,
  ScenariosResult,
  SubdivisionResult,
  ValuationResult,
  VerdictResult,
} from '@/lib/types'

export const useParcelStore = defineStore('parcel', () => {
  const detail = ref<ParcelDetail | null>(null)
  const focusTick = ref(0)
  const verdict = ref<VerdictResult | null>(null)
  const envelope = ref<EnvelopeResult | null>(null)
  const assemblage = ref<AssemblageResult | null>(null)
  const assemblageLoading = ref(false)
  const distress = ref<DistressResult | null>(null)
  const nextSheriffSale = ref<NextSheriffSale | null>(null)
  const subdivision = ref<SubdivisionResult | null>(null)
  const historic = ref<HistoricResult | null>(null)
  const scenarios = ref<ScenariosResult | null>(null)
  const comps = ref<ValuationResult | null>(null)
  const deal = ref<DealResult | null>(null)
  const dealLoading = ref(false)
  const underwriting = ref<UnderwritingAnalysis | null>(null)
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
    nextSheriffSale.value = null
    subdivision.value = null
    historic.value = null
    scenarios.value = null
    comps.value = null
    deal.value = null
    underwriting.value = null
    checklist.value = null
    ownerPortfolio.value = null
    deedRestrictions.value = null
    try {
      detail.value = await api.getParcel(parcelNumber)
      verdict.value = await loadVerdict(parcelNumber)
      void loadAssemblage(parcelNumber)
      void loadDistress(parcelNumber)
      void loadNextSheriffSale(parcelNumber)
      void loadSubdivision(parcelNumber)
      void loadHistoric(parcelNumber)
      void loadScenarios(parcelNumber)
      void loadComps(parcelNumber)
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
    // The verdict is computed when it is read, so a 404 means there is no such parcel.
    try {
      return await api.getVerdict(parcelNumber)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) return null
      throw cause
    }
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

  async function loadNextSheriffSale(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getNextSheriffSale(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) nextSheriffSale.value = result
    } catch {
      nextSheriffSale.value = null
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

  async function loadHistoric(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getHistoric(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) historic.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) historic.value = null
    }
  }

  async function loadScenarios(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getScenarios(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) scenarios.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) scenarios.value = null
    }
  }

  async function loadComps(parcelNumber: string): Promise<void> {
    try {
      const result = await api.getComps(parcelNumber)
      if (detail.value?.parcel_number === parcelNumber) comps.value = result
    } catch {
      if (detail.value?.parcel_number === parcelNumber) comps.value = null
    }
  }

  async function loadDeal(parcelNumber: string, overrides: DealOverrides = {}): Promise<void> {
    dealLoading.value = true
    try {
      const [dealResult, underwritingResult] = await Promise.allSettled([
        Promise.resolve().then(() => api.getDeal(parcelNumber, overrides)),
        Promise.resolve().then(() => api.getUnderwriting(parcelNumber, overrides)),
      ])
      if (detail.value?.parcel_number !== parcelNumber) return
      deal.value = dealResult.status === 'fulfilled' ? dealResult.value : null
      underwriting.value =
        underwritingResult.status === 'fulfilled' ? underwritingResult.value : null
    } catch {
      if (detail.value?.parcel_number === parcelNumber) {
        deal.value = null
        underwriting.value = null
      }
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
    nextSheriffSale.value = null
    subdivision.value = null
    historic.value = null
    scenarios.value = null
    comps.value = null
    deal.value = null
    underwriting.value = null
    checklist.value = null
    ownerPortfolio.value = null
    deedRestrictions.value = null
    error.value = null
    errorStatus.value = null
  }

  function focusOnMap(): void {
    focusTick.value += 1
  }

  return {
    detail,
    focusTick,
    verdict,
    envelope,
    assemblage,
    assemblageLoading,
    distress,
    nextSheriffSale,
    subdivision,
    historic,
    scenarios,
    comps,
    deal,
    underwriting,
    dealLoading,
    checklist,
    ownerPortfolio,
    deedRestrictions,
    loading,
    error,
    errorStatus,
    select,
    focusOnMap,
    loadEnvelope,
    loadAssemblage,
    loadDistress,
    loadSubdivision,
    loadHistoric,
    loadScenarios,
    loadComps,
    loadDeal,
    loadChecklist,
    loadOwnerPortfolio,
    loadDeedRestrictions,
    clear,
  }
})
