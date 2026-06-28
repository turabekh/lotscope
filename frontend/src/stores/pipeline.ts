import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '@/lib/api'
import type { DealItem, DealStage } from '@/lib/types'

export const STAGES: { value: DealStage; label: string; color: string }[] = [
  { value: 'lead', label: 'Lead', color: 'blue-grey-6' },
  { value: 'diligence', label: 'Diligence', color: 'indigo-6' },
  { value: 'offer', label: 'Offer', color: 'amber-8' },
  { value: 'under_contract', label: 'Under contract', color: 'teal-7' },
  { value: 'closed', label: 'Closed', color: 'positive' },
  { value: 'lost', label: 'Lost', color: 'grey-6' },
]

export const usePipelineStore = defineStore('pipeline', () => {
  const deals = ref<DealItem[]>([])
  const limit = ref<number | null>(null)
  const loaded = ref(false)
  const loading = ref(false)

  const dealNumbers = computed(() => new Set(deals.value.map((deal) => deal.parcel_number)))
  const used = computed(() => deals.value.length)
  const atLimit = computed(() => limit.value !== null && used.value >= limit.value)

  function dealFor(parcelNumber: string): DealItem | undefined {
    return deals.value.find((deal) => deal.parcel_number === parcelNumber)
  }

  function isInPipeline(parcelNumber: string): boolean {
    return dealNumbers.value.has(parcelNumber)
  }

  async function load(): Promise<void> {
    loading.value = true
    try {
      const response = await api.getPipeline()
      deals.value = response.deals
      limit.value = response.limit
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (!loaded.value && !loading.value) await load()
  }

  async function add(parcelNumber: string): Promise<void> {
    const deal = await api.addToPipeline(parcelNumber)
    if (!isInPipeline(parcelNumber)) deals.value = [deal, ...deals.value]
  }

  function _replace(updated: DealItem): void {
    deals.value = deals.value.map((deal) => (deal.id === updated.id ? updated : deal))
  }

  async function moveStage(parcelNumber: string, stage: DealStage): Promise<void> {
    const existing = dealFor(parcelNumber)
    if (!existing || existing.stage === stage) return
    const previous = existing.stage
    existing.stage = stage
    try {
      _replace(await api.updateDeal(parcelNumber, { stage }))
    } catch (cause) {
      existing.stage = previous
      throw cause
    }
  }

  async function updateDeal(
    parcelNumber: string,
    payload: { note?: string | null; target_price?: number | null },
  ): Promise<void> {
    _replace(await api.updateDeal(parcelNumber, payload))
  }

  async function remove(parcelNumber: string): Promise<void> {
    await api.removeFromPipeline(parcelNumber)
    deals.value = deals.value.filter((deal) => deal.parcel_number !== parcelNumber)
  }

  function reset(): void {
    deals.value = []
    limit.value = null
    loaded.value = false
  }

  return {
    deals,
    limit,
    loaded,
    loading,
    used,
    atLimit,
    dealFor,
    isInPipeline,
    load,
    ensureLoaded,
    add,
    moveStage,
    updateDeal,
    remove,
    reset,
  }
})
