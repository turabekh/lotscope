<script setup lang="ts">
import maplibregl, {
  type ExpressionSpecification,
  type FilterSpecification,
  type StyleSpecification,
} from 'maplibre-gl'
import { storeToRefs } from 'pinia'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useFiltersStore } from '@/stores/filters'
import { useParcelStore } from '@/stores/parcel'

const emit = defineEmits<{ select: [parcelNumber: string] }>()

const container = ref<HTMLDivElement | null>(null)
const martinUrl = import.meta.env.VITE_MARTIN_URL ?? 'http://localhost:3000'
const PHILADELPHIA: [number, number] = [-75.1652, 39.9526]

const { detail } = storeToRefs(useParcelStore())
const filters = useFiltersStore()
const { vacantOnly, useClasses } = storeToRefs(filters)
let map: maplibregl.Map | undefined

const baseStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

function parcelFilter(): FilterSpecification | null {
  const conditions: ExpressionSpecification[] = []
  if (vacantOnly.value) {
    conditions.push(['==', ['get', 'is_vacant'], true])
  }
  if (useClasses.value.length > 0 && useClasses.value.length < 4) {
    conditions.push([
      'in',
      ['upcase', ['slice', ['coalesce', ['get', 'base_zoning_code'], ''], 0, 1]],
      ['literal', useClasses.value],
    ])
  }
  if (conditions.length === 0) return null
  return ['all', ...conditions]
}

function addParcelLayers(instance: maplibregl.Map): void {
  instance.addSource('parcels', {
    type: 'vector',
    tiles: [`${martinUrl}/parcels_mvt/{z}/{x}/{y}`],
    minzoom: 12,
  })
  instance.addLayer({
    id: 'parcels-fill',
    type: 'fill',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: {
      'fill-color': ['case', ['==', ['get', 'is_vacant'], true], '#f9a825', '#1565c0'],
      'fill-opacity': ['case', ['==', ['get', 'is_vacant'], true], 0.5, 0.18],
    },
  })
  instance.addLayer({
    id: 'parcels-outline',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    minzoom: 15,
    paint: { 'line-color': '#90a4ae', 'line-width': 0.6 },
  })
  instance.addLayer({
    id: 'parcel-selected-fill',
    type: 'fill',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'fill-color': '#c62828', 'fill-opacity': 0.4 },
    filter: ['==', ['get', 'parcel_number'], ''],
  })
  instance.addLayer({
    id: 'parcel-selected',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'line-color': '#b71c1c', 'line-width': 3 },
    filter: ['==', ['get', 'parcel_number'], ''],
  })

  instance.setFilter('parcels-fill', parcelFilter())

  instance.on('click', 'parcels-fill', (event) => {
    const parcelNumber = event.features?.[0]?.properties?.parcel_number
    if (typeof parcelNumber === 'string') emit('select', parcelNumber)
  })
  instance.on('mouseenter', 'parcels-fill', () => {
    instance.getCanvas().style.cursor = 'pointer'
  })
  instance.on('mouseleave', 'parcels-fill', () => {
    instance.getCanvas().style.cursor = ''
  })
}

onMounted(() => {
  if (container.value === null) return
  map = new maplibregl.Map({
    container: container.value,
    style: baseStyle,
    center: PHILADELPHIA,
    zoom: 13,
  })
  map.addControl(new maplibregl.NavigationControl(), 'top-right')
  map.on('load', () => {
    if (map) addParcelLayers(map)
  })
})

watch([vacantOnly, useClasses], () => {
  if (map?.getLayer('parcels-fill')) map.setFilter('parcels-fill', parcelFilter())
})

watch(detail, (selected) => {
  if (!map || !map.getLayer('parcel-selected')) return
  const filter: FilterSpecification = [
    '==',
    ['get', 'parcel_number'],
    selected?.parcel_number ?? '',
  ]
  map.setFilter('parcel-selected', filter)
  map.setFilter('parcel-selected-fill', filter)
  if (selected && selected.longitude !== null && selected.latitude !== null) {
    map.flyTo({ center: [selected.longitude, selected.latitude], zoom: 17, duration: 900 })
  }
})

onBeforeUnmount(() => {
  map?.remove()
})
</script>

<template>
  <div ref="container" class="map-root" />
</template>

<style scoped>
.map-root {
  width: 100%;
  height: 100%;
  min-height: 300px;
}
</style>
