import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/lib/api'
import type { GeoPoint, SpatialParcelResult } from '@/lib/types'
import { useFiltersStore } from '@/stores/filters'

const DEFAULT_RADIUS_M = 500
const RESULT_LIMIT = 200

export type AreaShape = 'radius' | 'polygon'

export const useAreaSearchStore = defineStore('areaSearch', () => {
  const active = ref(false)
  const shape = ref<AreaShape>('radius')
  const center = ref<GeoPoint | null>(null)
  const polygon = ref<GeoJSON.Polygon | null>(null)
  const radiusM = ref(DEFAULT_RADIUS_M)
  const loading = ref(false)
  const results = ref<SpatialParcelResult[]>([])
  const count = ref(0)
  const truncated = ref(false)

  function clear(): void {
    center.value = null
    polygon.value = null
    results.value = []
    count.value = 0
    truncated.value = false
  }

  function toggle(): void {
    active.value = !active.value
    if (!active.value) clear()
  }

  function setShape(next: AreaShape): void {
    if (shape.value === next) return
    shape.value = next
    clear()
  }

  function applyResponse(response: {
    results: SpatialParcelResult[]
    count: number
    truncated: boolean
  }): void {
    results.value = response.results
    count.value = response.count
    truncated.value = response.truncated
  }

  async function run(): Promise<void> {
    if (center.value === null) return
    loading.value = true
    try {
      const filters = useFiltersStore()
      applyResponse(
        await api.searchArea({
          center: center.value,
          radius_m: radiusM.value,
          vacant_only: filters.vacantOnly,
          limit: RESULT_LIMIT,
        }),
      )
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

  async function searchPolygon(geometry: GeoJSON.Polygon): Promise<void> {
    polygon.value = geometry
    loading.value = true
    try {
      const filters = useFiltersStore()
      applyResponse(
        await api.searchArea({
          polygon: geometry,
          vacant_only: filters.vacantOnly,
          limit: RESULT_LIMIT,
        }),
      )
    } finally {
      loading.value = false
    }
  }

  function reset(): void {
    active.value = false
    shape.value = 'radius'
    radiusM.value = DEFAULT_RADIUS_M
    clear()
  }

  return {
    active,
    shape,
    center,
    polygon,
    radiusM,
    loading,
    results,
    count,
    truncated,
    clear,
    toggle,
    setShape,
    run,
    setCenter,
    setRadius,
    searchPolygon,
    reset,
  }
})
