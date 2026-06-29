import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '@/lib/api'
import type { SavedSearchDetail, SavedSearchItem, SearchCriteria } from '@/lib/types'

export function emptyCriteria(): SearchCriteria {
  return {
    vacant_only: false,
    exclude_city_owned: true,
    zoning_codes: [],
    zip_code: null,
    min_market_value: null,
    max_market_value: null,
    min_lot_area_sqft: null,
    max_lot_area_sqft: null,
    min_opportunity_score: null,
    min_distress_score: null,
    is_delinquent: null,
    in_sheriff_sale: null,
  }
}

export const useSavedSearchesStore = defineStore('savedSearches', () => {
  const searches = ref<SavedSearchItem[]>([])
  const limit = ref<number | null>(null)
  const loaded = ref(false)
  const loading = ref(false)

  const used = computed(() => searches.value.length)
  const atLimit = computed(() => limit.value !== null && used.value >= limit.value)
  const newTotal = computed(() => searches.value.reduce((sum, s) => sum + s.new_count, 0))

  async function load(): Promise<void> {
    loading.value = true
    try {
      const response = await api.getSavedSearches()
      searches.value = response.searches
      limit.value = response.limit
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (!loaded.value && !loading.value) await load()
  }

  async function create(payload: {
    name: string
    criteria: SearchCriteria
    alerts_enabled?: boolean
  }): Promise<SavedSearchDetail> {
    const detail = await api.createSavedSearch(payload)
    await load()
    return detail
  }

  async function remove(id: number): Promise<void> {
    await api.deleteSavedSearch(id)
    searches.value = searches.value.filter((s) => s.id !== id)
  }

  async function setAlerts(id: number, alertsEnabled: boolean): Promise<void> {
    const detail = await api.updateSavedSearch(id, { alerts_enabled: alertsEnabled })
    patch(detail)
  }

  async function run(id: number): Promise<SavedSearchDetail> {
    const detail = await api.runSavedSearch(id)
    patch(detail)
    return detail
  }

  function patch(detail: SavedSearchDetail): void {
    const item = searches.value.find((s) => s.id === detail.id)
    if (item) {
      item.alerts_enabled = detail.alerts_enabled
      item.match_count = detail.match_count
      item.new_count = detail.new_count
      item.last_run_at = detail.last_run_at
    }
  }

  function reset(): void {
    searches.value = []
    limit.value = null
    loaded.value = false
  }

  return {
    searches,
    limit,
    loaded,
    loading,
    used,
    atLimit,
    newTotal,
    load,
    ensureLoaded,
    create,
    remove,
    setAlerts,
    run,
    reset,
  }
})
