<script setup lang="ts">
import maplibregl, { type StyleSpecification } from 'maplibre-gl'
import { storeToRefs } from 'pinia'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const emit = defineEmits<{ select: [parcelNumber: string] }>()

const container = ref<HTMLDivElement | null>(null)
const martinUrl = import.meta.env.VITE_MARTIN_URL ?? 'http://localhost:3000'
const PHILADELPHIA: [number, number] = [-75.1652, 39.9526]

const { detail } = storeToRefs(useParcelStore())
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
    paint: { 'fill-color': '#1565c0', 'fill-opacity': 0.12, 'fill-outline-color': '#1565c0' },
  })
  instance.addSource('vacant', {
    type: 'vector',
    tiles: [`${martinUrl}/vacant_lots_mvt/{z}/{x}/{y}`],
    minzoom: 12,
  })
  instance.addLayer({
    id: 'vacant-fill',
    type: 'fill',
    source: 'vacant',
    'source-layer': 'vacant_lots',
    paint: { 'fill-color': '#f9a825', 'fill-opacity': 0.45 },
  })
  instance.addLayer({
    id: 'parcel-selected',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'line-color': '#c62828', 'line-width': 3 },
    filter: ['==', ['get', 'parcel_number'], ''],
  })

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

watch(detail, (selected) => {
  if (!map || !map.getLayer('parcel-selected')) return
  map.setFilter('parcel-selected', [
    '==',
    ['get', 'parcel_number'],
    selected?.parcel_number ?? '',
  ])
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
