import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/lib/api'
import type { AreaSearchRequest, GeoPoint, SpatialParcelResult } from '@/lib/types'
import { useFiltersStore } from '@/stores/filters'

const DEFAULT_RADIUS_M = 500
const RESULT_LIMIT = 200

export type AreaShape = 'radius' | 'polygon' | 'neighborhood'

export const useAreaSearchStore = defineStore('areaSearch', () => {
  const active = ref(false)
  const shape = ref<AreaShape>('radius')
  const center = ref<GeoPoint | null>(null)
  const polygon = ref<GeoJSON.Polygon | null>(null)
  const neighborhood = ref<string | null>(null)
  const neighborhoods = ref<string[]>([])
  const radiusM = ref(DEFAULT_RADIUS_M)
  const minValue = ref<number | null>(null)
  const maxValue = ref<number | null>(null)
  const minLotArea = ref<number | null>(null)
  const maxLotArea = ref<number | null>(null)
  const minScore = ref<number | null>(null)
  const loading = ref(false)
  const results = ref<SpatialParcelResult[]>([])
  const count = ref(0)
  const truncated = ref(false)

  function criteria(): Partial<AreaSearchRequest> {
    const c: Partial<AreaSearchRequest> = { vacant_only: useFiltersStore().vacantOnly }
    if (minValue.value !== null) c.min_market_value = minValue.value
    if (maxValue.value !== null) c.max_market_value = maxValue.value
    if (minLotArea.value !== null) c.min_lot_area_sqft = minLotArea.value
    if (maxLotArea.value !== null) c.max_lot_area_sqft = maxLotArea.value
    if (minScore.value !== null) c.min_opportunity_score = minScore.value
    return c
  }

  function clear(): void {
    center.value = null
    polygon.value = null
    neighborhood.value = null
    results.value = []
    count.value = 0
    truncated.value = false
  }

  async function loadNeighborhoods(): Promise<void> {
    if (neighborhoods.value.length > 0) return
    const response = await api.getNeighborhoods()
    neighborhoods.value = response.neighborhoods.map((item) => item.name)
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
      applyResponse(
        await api.searchArea({
          center: center.value,
          radius_m: radiusM.value,
          ...criteria(),
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
      applyResponse(
        await api.searchArea({
          polygon: geometry,
          ...criteria(),
          limit: RESULT_LIMIT,
        }),
      )
    } finally {
      loading.value = false
    }
  }

  async function searchViewport(rect: GeoJSON.Polygon): Promise<void> {
    loading.value = true
    try {
      applyResponse(await api.searchArea({ polygon: rect, ...criteria(), limit: RESULT_LIMIT }))
    } finally {
      loading.value = false
    }
  }

  function clearResults(): void {
    results.value = []
    count.value = 0
    truncated.value = false
  }

  async function searchNeighborhood(name: string): Promise<void> {
    neighborhood.value = name
    loading.value = true
    try {
      applyResponse(
        await api.searchArea({
          neighborhood: name,
          ...criteria(),
          limit: RESULT_LIMIT,
        }),
      )
    } finally {
      loading.value = false
    }
  }

  async function rerun(): Promise<void> {
    if (shape.value === 'radius' && center.value !== null) await run()
    else if (shape.value === 'polygon' && polygon.value !== null) await searchPolygon(polygon.value)
    else if (shape.value === 'neighborhood' && neighborhood.value !== null)
      await searchNeighborhood(neighborhood.value)
  }

  function reset(): void {
    active.value = false
    shape.value = 'radius'
    radiusM.value = DEFAULT_RADIUS_M
    minValue.value = null
    maxValue.value = null
    minLotArea.value = null
    maxLotArea.value = null
    minScore.value = null
    clear()
  }

  return {
    active,
    shape,
    center,
    polygon,
    neighborhood,
    neighborhoods,
    radiusM,
    minValue,
    maxValue,
    minLotArea,
    maxLotArea,
    minScore,
    loading,
    results,
    count,
    truncated,
    clear,
    toggle,
    setShape,
    loadNeighborhoods,
    run,
    setCenter,
    setRadius,
    searchPolygon,
    searchNeighborhood,
    searchViewport,
    clearResults,
    rerun,
    reset,
  }
})
