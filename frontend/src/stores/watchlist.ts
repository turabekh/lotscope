import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '@/lib/api'
import type { WatchlistItem } from '@/lib/types'

export const useWatchlistStore = defineStore('watchlist', () => {
  const items = ref<WatchlistItem[]>([])
  const limit = ref<number | null>(null)
  const loaded = ref(false)
  const loading = ref(false)

  const savedNumbers = computed(() => new Set(items.value.map((item) => item.parcel_number)))
  const used = computed(() => items.value.length)
  const atLimit = computed(() => limit.value !== null && used.value >= limit.value)
  const alerts = computed(() => items.value.filter((item) => item.has_alerts).length)

  function isSaved(parcelNumber: string): boolean {
    return savedNumbers.value.has(parcelNumber)
  }

  async function load(): Promise<void> {
    loading.value = true
    try {
      const response = await api.getWatchlist()
      items.value = response.items
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
    await api.addToWatchlist(parcelNumber)
    await load()
  }

  async function remove(parcelNumber: string): Promise<void> {
    await api.removeFromWatchlist(parcelNumber)
    items.value = items.value.filter((item) => item.parcel_number !== parcelNumber)
  }

  async function updateItem(
    parcelNumber: string,
    payload: { tags?: string[]; note?: string | null },
  ): Promise<void> {
    await api.updateWatchlistItem(parcelNumber, payload)
    const item = items.value.find((entry) => entry.parcel_number === parcelNumber)
    if (item) {
      if (payload.tags !== undefined) item.tags = payload.tags
      if (payload.note !== undefined) item.note = payload.note
    }
  }

  async function markSeen(parcelNumber: string): Promise<void> {
    await api.markWatchlistSeen(parcelNumber)
    const item = items.value.find((entry) => entry.parcel_number === parcelNumber)
    if (item) {
      item.changes = []
      item.has_alerts = false
    }
  }

  function reset(): void {
    items.value = []
    limit.value = null
    loaded.value = false
  }

  return {
    items,
    limit,
    loaded,
    loading,
    savedNumbers,
    used,
    atLimit,
    alerts,
    isSaved,
    load,
    ensureLoaded,
    add,
    remove,
    updateItem,
    markSeen,
    reset,
  }
})
