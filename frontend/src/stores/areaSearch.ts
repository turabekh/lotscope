import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/lib/api'
import type { GeoPoint, SpatialParcelResult } from '@/lib/types'
import { useFiltersStore } from '@/stores/filters'

const DEFAULT_RADIUS_M = 500
const RESULT_LIMIT = 200

export const useAreaSearchStore = defineStore('areaSearch', () => {
  const active = ref(false)
  const center = ref<GeoPoint | null>(null)
  const radiusM = ref(DEFAULT_RADIUS_M)
  const loading = ref(false)
  const results = ref<SpatialParcelResult[]>([])
  const count = ref(0)
  const truncated = ref(false)

  function clear(): void {
    center.value = null
    results.value = []
    count.value = 0
    truncated.value = false
  }

  function toggle(): void {
    active.value = !active.value
    if (!active.value) clear()
  }

  async function run(): Promise<void> {
    if (center.value === null) return
    loading.value = true
    try {
      const filters = useFiltersStore()
      const response = await api.searchArea({
        center: center.value,
        radius_m: radiusM.value,
        vacant_only: filters.vacantOnly,
        limit: RESULT_LIMIT,
      })
      results.value = response.results
      count.value = response.count
      truncated.value = response.truncated
    } finally {
      loading.value = false
    }
  }

  async function setCenter(point: GeoPoint): Promise<void> {
    center.value = point
    await run()
  }

  async function setRadius(meters: number): Promise<void> {
    radiusM.value = meters
    if (center.value !== null) await run()
  }

  function reset(): void {
    active.value = false
    radiusM.value = DEFAULT_RADIUS_M
    clear()
  }

  return {
    active,
    center,
    radiusM,
    loading,
    results,
    count,
    truncated,
    clear,
    toggle,
    run,
    setCenter,
    setRadius,
    reset,
  }
})
