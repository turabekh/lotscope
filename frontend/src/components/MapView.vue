<script setup lang="ts">
import maplibregl, {
  type ExpressionSpecification,
  type FilterSpecification,
  type MapLayerMouseEvent,
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
const { vacantOnly, useClasses, colorMode } = storeToRefs(filters)
let map: maplibregl.Map | undefined
const popup = new maplibregl.Popup({
  closeButton: false,
  closeOnClick: false,
  offset: 12,
  className: 'lot-popup',
})

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

function classCondition(): ExpressionSpecification | null {
  if (useClasses.value.length === 0 || useClasses.value.length >= 4) return null
  return [
    'in',
    ['upcase', ['slice', ['coalesce', ['get', 'base_zoning_code'], ''], 0, 1]],
    ['literal', useClasses.value],
  ]
}

function parcelFilter(): FilterSpecification | null {
  const conditions: ExpressionSpecification[] = []
  if (vacantOnly.value) conditions.push(['==', ['get', 'is_vacant'], true])
  const cls = classCondition()
  if (cls) conditions.push(cls)
  return conditions.length === 0 ? null : ['all', ...conditions]
}

function markerFilter(): FilterSpecification {
  const conditions: ExpressionSpecification[] = [['==', ['get', 'is_vacant'], true]]
  const cls = classCondition()
  if (cls) conditions.push(cls)
  return ['all', ...conditions]
}

function fillColor(): ExpressionSpecification {
  if (colorMode.value === 'opportunity') {
    return [
      'interpolate',
      ['linear'],
      ['coalesce', ['get', 'opportunity_score'], 0],
      0,
      '#c62828',
      45,
      '#f9a825',
      65,
      '#9ccc65',
      100,
      '#2e7d32',
    ]
  }
  if (colorMode.value === 'risk') {
    return [
      'interpolate',
      ['linear'],
      ['coalesce', ['get', 'risk_score'], 0],
      0,
      '#2e7d32',
      25,
      '#9ccc65',
      50,
      '#f9a825',
      100,
      '#c62828',
    ]
  }
  return ['case', ['==', ['get', 'is_vacant'], true], '#f9a825', '#1565c0']
}

function fillOpacity(): ExpressionSpecification {
  if (colorMode.value === 'opportunity') return ['case', ['has', 'opportunity_score'], 0.72, 0]
  if (colorMode.value === 'risk') return ['case', ['has', 'risk_score'], 0.72, 0]
  return ['case', ['==', ['get', 'is_vacant'], true], 0.55, 0.16]
}

function applyFillPaint(): void {
  if (!map?.getLayer('parcels-fill')) return
  map.setPaintProperty('parcels-fill', 'fill-color', fillColor())
  map.setPaintProperty('parcels-fill', 'fill-opacity', fillOpacity())
}

function dotImage(diameter: number, fill: string): ImageData {
  const canvas = document.createElement('canvas')
  canvas.width = diameter
  canvas.height = diameter
  const ctx = canvas.getContext('2d')
  if (ctx === null) return new ImageData(diameter, diameter)
  const radius = diameter / 2
  ctx.beginPath()
  ctx.arc(radius, radius, radius - 4, 0, Math.PI * 2)
  ctx.fillStyle = fill
  ctx.fill()
  ctx.lineWidth = 3
  ctx.strokeStyle = '#ffffff'
  ctx.stroke()
  return ctx.getImageData(0, 0, diameter, diameter)
}

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"]/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char] ?? char,
  )
}

function compactMoney(value: unknown): string {
  if (typeof value !== 'number') return '—'
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`
  return `$${value}`
}

function popupHtml(properties: Record<string, unknown>): string {
  const address = escapeHtml(String(properties.address ?? properties.parcel_number ?? 'Parcel'))
  const zoning = escapeHtml(String(properties.base_zoning_code ?? '—'))
  const vacant = properties.is_vacant === true || properties.is_vacant === 'true'
  const vacantTag = vacant ? '<span class="lp-vac">VACANT</span>' : ''
  const opportunity = properties.opportunity_score
  let rows = ''
  if (typeof opportunity === 'number') {
    rows += `<div class="lp-score">Opportunity <b>${Math.round(opportunity)}</b>`
    rows += `<span class="lp-risk">· Risk ${Math.round(Number(properties.risk_score ?? 0))}</span></div>`
    const units = properties.by_right_units
    const byRight =
      typeof units === 'number'
        ? `${units} unit${units === 1 ? '' : 's'} by-right`
        : properties.can_build_by_right === false
          ? 'Not by-right'
          : ''
    const value =
      typeof properties.value_low === 'number'
        ? `${compactMoney(properties.value_low)}–${compactMoney(properties.value_high)}`
        : ''
    if (byRight || value) {
      rows += `<div class="lp-extra">${[byRight, value].filter(Boolean).join(' · ')}</div>`
    }
  }
  return (
    `<div class="lot-pop"><div class="lp-addr">${address}</div>` +
    `<div class="lp-meta"><span class="lp-zone">${zoning}</span>${vacantTag}</div>` +
    `${rows}<div class="lp-hint">Click for the full verdict</div></div>`
  )
}

function showPopup(event: MapLayerMouseEvent): void {
  const feature = event.features?.[0]
  if (!feature || !map) return
  map.getCanvas().style.cursor = 'pointer'
  popup
    .setLngLat(event.lngLat)
    .setHTML(popupHtml(feature.properties ?? {}))
    .addTo(map)
}

function hidePopup(): void {
  if (map) map.getCanvas().style.cursor = ''
  popup.remove()
}

function selectFromEvent(event: MapLayerMouseEvent): void {
  const parcelNumber = event.features?.[0]?.properties?.parcel_number
  if (typeof parcelNumber === 'string') emit('select', parcelNumber)
}

function addParcelLayers(instance: maplibregl.Map): void {
  if (!instance.hasImage('lot-dot-vacant')) {
    instance.addImage('lot-dot-vacant', dotImage(36, '#f9a825'), { pixelRatio: 2 })
  }
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
      'fill-opacity': ['case', ['==', ['get', 'is_vacant'], true], 0.55, 0.16],
    },
  })
  instance.addLayer({
    id: 'parcels-outline',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    minzoom: 15,
    paint: { 'line-color': '#90a4ae', 'line-width': 0.5 },
  })
  instance.addLayer({
    id: 'vacant-outline',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    minzoom: 14,
    filter: ['==', ['get', 'is_vacant'], true],
    paint: { 'line-color': '#ef6c00', 'line-width': 1.6 },
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
  instance.addLayer({
    id: 'vacant-markers',
    type: 'symbol',
    source: 'parcels',
    'source-layer': 'parcels',
    minzoom: 12,
    filter: markerFilter(),
    layout: {
      'icon-image': 'lot-dot-vacant',
      'icon-allow-overlap': false,
      'icon-ignore-placement': false,
      'icon-size': ['interpolate', ['linear'], ['zoom'], 12, 0.32, 16, 0.62, 19, 0.95],
    },
  })

  instance.setFilter('parcels-fill', parcelFilter())
  applyFillPaint()

  for (const layer of ['parcels-fill', 'vacant-markers']) {
    instance.on('click', layer, selectFromEvent)
    instance.on('mousemove', layer, showPopup)
    instance.on('mouseleave', layer, hidePopup)
  }
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
  if (!map?.getLayer('parcels-fill')) return
  map.setFilter('parcels-fill', parcelFilter())
  map.setFilter('vacant-markers', markerFilter())
})

watch(colorMode, applyFillPaint)

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
  popup.remove()
  map?.remove()
})
</script>

<template>
  <div ref="container" class="map-root" />
</template>

<style scoped>
.map-root {
  position: absolute;
  inset: 0;
  min-height: 300px;
}
</style>

<style>
.lot-popup .maplibregl-popup-content {
  padding: 8px 11px;
  border-radius: 9px;
  box-shadow: 0 3px 14px rgba(0, 0, 0, 0.2);
}
.lot-pop .lp-addr {
  font-weight: 600;
  font-size: 13px;
  color: #1a1a1a;
}
.lot-pop .lp-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
}
.lot-pop .lp-zone {
  background: #eceff1;
  color: #37474f;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 600;
}
.lot-pop .lp-vac {
  background: #f9a825;
  color: #fff;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.lot-pop .lp-score {
  font-size: 12px;
  color: #37474f;
  margin-top: 4px;
}
.lot-pop .lp-score .lp-risk {
  color: #90a4ae;
  margin-left: 4px;
}
.lot-pop .lp-extra {
  font-size: 12px;
  color: #455a64;
  margin-top: 2px;
}
.lot-pop .lp-hint {
  font-size: 11px;
  color: #90a4ae;
  margin-top: 5px;
}
</style>
