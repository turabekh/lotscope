<script setup lang="ts">
import maplibregl, {
  type ExpressionSpecification,
  type FilterSpecification,
  type MapLayerMouseEvent,
  type StyleSpecification,
} from 'maplibre-gl'
import { storeToRefs } from 'pinia'
import { TerraDraw, TerraDrawPolygonMode } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { api } from '@/lib/api'
import type { MapBounds } from '@/lib/explore'
import { useAreaSearchStore } from '@/stores/areaSearch'
import { useFiltersStore } from '@/stores/filters'
import { useParcelStore } from '@/stores/parcel'

const emit = defineEmits<{
  select: [parcelNumber: string]
  boundschange: [bounds: MapBounds]
}>()

function emitBounds(): void {
  if (!map) return
  const b = map.getBounds()
  emit('boundschange', {
    north: b.getNorth(),
    south: b.getSouth(),
    east: b.getEast(),
    west: b.getWest(),
    zoom: map.getZoom(),
  })
}

const areaSearch = useAreaSearchStore()
const {
  active: areaActive,
  shape: areaShape,
  center: areaCenter,
  radiusM: areaRadius,
  results: areaResults,
} = storeToRefs(areaSearch)
const EARTH_RADIUS_M = 6378137
let draw: TerraDraw | undefined
let drawStarted = false

const container = ref<HTMLDivElement | null>(null)
const martinUrl = import.meta.env.VITE_MARTIN_URL ?? 'http://localhost:3000'
const PHILADELPHIA: [number, number] = [-75.1652, 39.9526]

const parcelStore = useParcelStore()
const { detail, envelope, assemblage } = storeToRefs(parcelStore)
const ACQUIRABILITY_COLOR: Record<string, string> = {
  same_owner: '#8e24aa',
  city_owned: '#ef6c00',
  vacant: '#00897b',
  built: '#90a4ae',
}
const EMPTY_PARCEL_FILTER: FilterSpecification = ['in', ['get', 'parcel_number'], ['literal', ['']]]
const filters = useFiltersStore()
const { vacantOnly, useClasses, colorMode, show3d, basemap } = storeToRefs(filters)
const FEET_TO_METERS = 0.3048
const OSM_TILES = ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']
const OSM_ATTRIBUTION = '© OpenStreetMap contributors'
const attributionText = ref(OSM_ATTRIBUTION)
let attributionTimer: ReturnType<typeof setTimeout> | undefined

async function updateAttribution(): Promise<void> {
  if (!map) return
  if (basemap.value === 'osm') {
    attributionText.value = OSM_ATTRIBUTION
    return
  }
  const bounds = map.getBounds()
  try {
    const result = await api.getBasemapAttribution(
      basemap.value,
      {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest(),
      },
      Math.round(map.getZoom()),
    )
    attributionText.value = result.attribution
  } catch {
    attributionText.value = 'Map data © Google'
  }
}

function scheduleAttributionUpdate(): void {
  if (basemap.value === 'osm') return
  if (attributionTimer) clearTimeout(attributionTimer)
  attributionTimer = setTimeout(() => void updateAttribution(), 400)
}

const envelopeCaption = computed(() => {
  const env = envelope.value
  if (!show3d.value || env === null) return null
  if (!env.available) return env.reasons[0] ?? 'No by-right height recorded for this district.'
  const height = env.max_height_ft !== null ? `${Math.round(env.max_height_ft)} ft` : ''
  const floors =
    env.estimated_floors !== null
      ? `~${env.estimated_floors} floor${env.estimated_floors === 1 ? '' : 's'}`
      : ''
  return [env.district_code ?? '', height, floors].filter(Boolean).join(' · ')
})
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
    basemap: {
      type: 'raster',
      tiles: OSM_TILES,
      tileSize: 256,
      attribution: OSM_ATTRIBUTION,
    },
  },
  layers: [{ id: 'basemap-layer', type: 'raster', source: 'basemap' }],
}

async function applyBasemap(id: 'satellite' | 'roadmap' | 'osm'): Promise<void> {
  if (!map) return
  let tiles = OSM_TILES
  let tileSize = 256
  if (id === 'satellite' || id === 'roadmap') {
    try {
      const session = await api.getBasemapSession(id)
      tiles = [session.tile_url]
      tileSize = session.tile_size
    } catch {
      if (basemap.value !== 'osm') basemap.value = 'osm'
      return
    }
  }
  if (!map) return
  if (map.getLayer('basemap-layer')) map.removeLayer('basemap-layer')
  if (map.getSource('basemap')) map.removeSource('basemap')
  map.addSource('basemap', { type: 'raster', tiles, tileSize })
  const below = map.getLayer('parcels-fill') ? 'parcels-fill' : undefined
  map.addLayer({ id: 'basemap-layer', type: 'raster', source: 'basemap' }, below)
  void updateAttribution()
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

function markerIcon(): ExpressionSpecification | string {
  if (colorMode.value === 'risk') {
    return [
      'step',
      ['coalesce', ['get', 'risk_score'], -1],
      'pin-none',
      0,
      'pin-top',
      25,
      'pin-high',
      50,
      'pin-mid',
      75,
      'pin-low',
    ]
  }
  if (colorMode.value === 'opportunity') {
    return [
      'step',
      ['coalesce', ['get', 'opportunity_score'], -1],
      'pin-none',
      0,
      'pin-low',
      45,
      'pin-mid',
      65,
      'pin-high',
      80,
      'pin-top',
    ]
  }
  return 'pin-vacant'
}

function applyMarkerIcon(): void {
  if (map?.getLayer('vacant-markers')) {
    map.setLayoutProperty('vacant-markers', 'icon-image', markerIcon())
  }
}

const MARKER_PINS: { id: string; color: string }[] = [
  { id: 'pin-none', color: '#9e9e9e' },
  { id: 'pin-low', color: '#e53935' },
  { id: 'pin-mid', color: '#fb8c00' },
  { id: 'pin-high', color: '#7cb342' },
  { id: 'pin-top', color: '#2e7d32' },
  { id: 'pin-vacant', color: '#f9a825' },
]

function lightenColor(hex: string, amount: number): string {
  const value = parseInt(hex.slice(1), 16)
  const r = (value >> 16) & 255
  const g = (value >> 8) & 255
  const b = value & 255
  const mix = (channel: number): number => Math.round(channel + (255 - channel) * amount)
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`
}

function pinImage(head: number, color: string): ImageData {
  const radius = head / 2
  const stroke = Math.max(2.5, head * 0.085)
  const pad = Math.ceil(stroke + 6)
  const width = head + pad * 2
  const cx = width / 2
  const cy = radius + pad
  const tipY = cy + radius * 1.95
  const height = Math.ceil(tipY + pad)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (ctx === null) return new ImageData(width, height)

  const balloon = new Path2D()
  const alpha = Math.acos(radius / (tipY - cy))
  const a1 = Math.PI / 2 + alpha
  const a2 = Math.PI / 2 - alpha
  balloon.moveTo(cx + radius * Math.cos(a1), cy + radius * Math.sin(a1))
  balloon.arc(cx, cy, radius, a1, a2 + Math.PI * 2, false)
  balloon.lineTo(cx, tipY)
  balloon.closePath()

  ctx.save()
  ctx.filter = 'blur(2.5px)'
  ctx.beginPath()
  ctx.ellipse(cx, tipY - 1, radius * 0.55, radius * 0.22, 0, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(15, 23, 42, 0.35)'
  ctx.fill()
  ctx.restore()

  ctx.lineJoin = 'round'
  ctx.lineWidth = stroke
  ctx.strokeStyle = '#ffffff'
  ctx.stroke(balloon)

  const gradient = ctx.createLinearGradient(cx, cy - radius, cx, tipY)
  gradient.addColorStop(0, lightenColor(color, 0.34))
  gradient.addColorStop(1, color)
  ctx.fillStyle = gradient
  ctx.fill(balloon)

  ctx.beginPath()
  ctx.ellipse(
    cx - radius * 0.26,
    cy - radius * 0.34,
    radius * 0.46,
    radius * 0.3,
    -0.5,
    0,
    Math.PI * 2,
  )
  ctx.fillStyle = 'rgba(255, 255, 255, 0.32)'
  ctx.fill()

  ctx.beginPath()
  ctx.arc(cx, cy, radius * 0.34, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  return ctx.getImageData(0, 0, width, height)
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
  const maxHeight = properties.max_height_ft
  if (typeof maxHeight === 'number' && maxHeight > 0) {
    const floors = Math.max(1, Math.floor(maxHeight / 10.5))
    rows += `<div class="lp-extra">Up to ${maxHeight} ft · ~${floors} floor${floors === 1 ? '' : 's'} by-right</div>`
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
  if (areaActive.value) return
  const parcelNumber = event.features?.[0]?.properties?.parcel_number
  if (typeof parcelNumber === 'string') emit('select', parcelNumber)
}

function onMapClick(event: MapLayerMouseEvent): void {
  if (!areaActive.value || areaShape.value !== 'radius') return
  hidePopup()
  void areaSearch.setCenter({ lat: event.lngLat.lat, lng: event.lngLat.lng })
}

function onPolygonFinish(id: string | number): void {
  if (!draw) return
  const feature = draw.getSnapshotFeature(id)
  if (feature === undefined || feature.geometry.type !== 'Polygon') return
  const stale = draw
    .getSnapshot()
    .map((item) => item.id)
    .filter((other): other is string | number => other !== undefined && other !== id)
  if (stale.length > 0) draw.removeFeatures(stale)
  void areaSearch.searchPolygon(feature.geometry)
}

function ensureDraw(): void {
  if (draw || !map) return
  draw = new TerraDraw({
    adapter: new TerraDrawMapLibreGLAdapter({ map }),
    modes: [new TerraDrawPolygonMode()],
  })
  draw.on('finish', onPolygonFinish)
}

function syncDraw(): void {
  if (!map) return
  if (areaActive.value && areaShape.value === 'polygon') {
    ensureDraw()
    if (draw && !drawStarted) {
      draw.start()
      drawStarted = true
    }
    draw?.setMode('polygon')
  } else if (draw && drawStarted) {
    draw.clear()
    draw.stop()
    drawStarted = false
  }
}

function circleFeature(): GeoJSON.FeatureCollection {
  const point = areaCenter.value
  if (!areaActive.value || areaShape.value !== 'radius' || point === null) return emptyCollection()
  const steps = 72
  const latRad = (point.lat * Math.PI) / 180
  const ring: [number, number][] = []
  for (let i = 0; i <= steps; i += 1) {
    const theta = (i / steps) * 2 * Math.PI
    const dLng =
      ((areaRadius.value * Math.cos(theta)) / (EARTH_RADIUS_M * Math.cos(latRad))) * (180 / Math.PI)
    const dLat = ((areaRadius.value * Math.sin(theta)) / EARTH_RADIUS_M) * (180 / Math.PI)
    ring.push([point.lng + dLng, point.lat + dLat])
  }
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [ring] } },
    ],
  }
}

function renderAreaCircle(): void {
  const source = map?.getSource('area-circle')
  if (source instanceof maplibregl.GeoJSONSource) source.setData(circleFeature())
}

function applyAreaResults(): void {
  if (!map?.getLayer('area-results-line')) return
  const ids = areaResults.value.map((result) => result.parcel_number)
  const filter: FilterSpecification =
    ids.length === 0 ? EMPTY_PARCEL_FILTER : ['in', ['get', 'parcel_number'], ['literal', ids]]
  map.setFilter('area-results-fill', filter)
  map.setFilter('area-results-line', filter)
}

function applyAreaCursor(): void {
  if (!map) return
  map.getCanvas().style.cursor = areaActive.value && areaShape.value === 'radius' ? 'crosshair' : ''
}

function emptyCollection(): GeoJSON.FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

function renderEnvelope(): void {
  const source = map?.getSource('envelope')
  if (!(source instanceof maplibregl.GeoJSONSource)) return
  const env = envelope.value
  if (!show3d.value || env === null || env.buildable_footprint === null) {
    source.setData(emptyCollection())
    return
  }
  const heightMeters = env.max_height_ft !== null ? env.max_height_ft * FEET_TO_METERS : 0
  source.setData({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { height_m: heightMeters },
        geometry: env.buildable_footprint,
      },
    ],
  })
}

function applyPitch(): void {
  if (!map || map.isMoving()) return
  const target = show3d.value ? 55 : 0
  if (Math.round(map.getPitch()) !== target) {
    map.easeTo({ pitch: target, duration: 600 })
  }
}

function applyAssemblage(): void {
  if (!map?.getLayer('assemblage-fill')) return
  const candidates = (assemblage.value?.neighbors ?? []).filter((lot) => lot.is_candidate)
  if (candidates.length === 0) {
    map.setFilter('assemblage-fill', EMPTY_PARCEL_FILTER)
    map.setFilter('assemblage-line', EMPTY_PARCEL_FILTER)
    return
  }
  const ids = candidates.map((lot) => lot.parcel_number)
  const colorMatch: unknown[] = ['match', ['get', 'parcel_number']]
  for (const lot of candidates) {
    colorMatch.push(lot.parcel_number, ACQUIRABILITY_COLOR[lot.acquirability] ?? '#90a4ae')
  }
  colorMatch.push('#90a4ae')
  const filter: FilterSpecification = ['in', ['get', 'parcel_number'], ['literal', ids]]
  const color = colorMatch as unknown as ExpressionSpecification
  map.setFilter('assemblage-fill', filter)
  map.setFilter('assemblage-line', filter)
  map.setPaintProperty('assemblage-fill', 'fill-color', color)
  map.setPaintProperty('assemblage-line', 'line-color', color)
}

function focusSelected(): void {
  if (!map || !map.getLayer('parcel-selected')) return
  const selected = detail.value
  const filter: FilterSpecification = [
    '==',
    ['get', 'parcel_number'],
    selected?.parcel_number ?? '',
  ]
  map.setFilter('parcel-selected', filter)
  map.setFilter('parcel-selected-fill', filter)
  if (selected && selected.longitude !== null && selected.latitude !== null) {
    map.flyTo({
      center: [selected.longitude, selected.latitude],
      zoom: 18.5,
      pitch: show3d.value ? 55 : map.getPitch(),
      duration: 1000,
      essential: true,
    })
  }
}

function addParcelLayers(instance: maplibregl.Map): void {
  for (const pin of MARKER_PINS) {
    if (!instance.hasImage(pin.id)) {
      instance.addImage(pin.id, pinImage(44, pin.color), { pixelRatio: 2 })
    }
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
    id: 'assemblage-fill',
    type: 'fill',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'fill-color': '#8e24aa', 'fill-opacity': 0.32 },
    filter: EMPTY_PARCEL_FILTER,
  })
  instance.addLayer({
    id: 'assemblage-line',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'line-color': '#8e24aa', 'line-width': 2.5, 'line-dasharray': [2, 1] },
    filter: EMPTY_PARCEL_FILTER,
  })
  instance.addLayer({
    id: 'area-results-fill',
    type: 'fill',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'fill-color': '#1565c0', 'fill-opacity': 0.4 },
    filter: EMPTY_PARCEL_FILTER,
  })
  instance.addLayer({
    id: 'area-results-line',
    type: 'line',
    source: 'parcels',
    'source-layer': 'parcels',
    paint: { 'line-color': '#0d47a1', 'line-width': 2 },
    filter: EMPTY_PARCEL_FILTER,
  })

  instance.addSource('area-circle', { type: 'geojson', data: emptyCollection() })
  instance.addLayer({
    id: 'area-circle-fill',
    type: 'fill',
    source: 'area-circle',
    paint: { 'fill-color': '#1565c0', 'fill-opacity': 0.08 },
  })
  instance.addLayer({
    id: 'area-circle-line',
    type: 'line',
    source: 'area-circle',
    paint: { 'line-color': '#1565c0', 'line-width': 2, 'line-dasharray': [2, 1] },
  })

  instance.addLayer({
    id: 'vacant-markers',
    type: 'symbol',
    source: 'parcels',
    'source-layer': 'parcels',
    minzoom: 12,
    filter: markerFilter(),
    layout: {
      'icon-image': markerIcon(),
      'icon-anchor': 'bottom',
      'icon-allow-overlap': false,
      'icon-ignore-placement': false,
      'icon-size': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 16, 0.85, 19, 1.15],
    },
  })

  instance.addSource('envelope', { type: 'geojson', data: emptyCollection() })
  instance.addLayer({
    id: 'envelope-extrusion',
    type: 'fill-extrusion',
    source: 'envelope',
    paint: {
      'fill-extrusion-color': '#1565c0',
      'fill-extrusion-height': ['coalesce', ['get', 'height_m'], 0],
      'fill-extrusion-base': 0,
      'fill-extrusion-opacity': 0.6,
    },
  })
  instance.addLayer({
    id: 'envelope-outline',
    type: 'line',
    source: 'envelope',
    paint: { 'line-color': '#0d47a1', 'line-width': 2 },
  })

  instance.setFilter('parcels-fill', parcelFilter())
  applyFillPaint()
  applyAssemblage()

  for (const layer of ['parcels-fill', 'vacant-markers']) {
    instance.on('click', layer, selectFromEvent)
    instance.on('mousemove', layer, showPopup)
    instance.on('mouseleave', layer, hidePopup)
  }
  instance.on('click', onMapClick)
}

onMounted(() => {
  if (container.value === null) return
  map = new maplibregl.Map({
    container: container.value,
    style: baseStyle,
    center: PHILADELPHIA,
    zoom: 13,
    attributionControl: false,
  })
  map.addControl(new maplibregl.NavigationControl(), 'top-right')
  map.on('load', () => {
    if (!map) return
    addParcelLayers(map)
    void applyBasemap(basemap.value)
    focusSelected()
    applyAssemblage()
    if (show3d.value && detail.value !== null) void parcelStore.loadEnvelope()
    renderEnvelope()
    applyPitch()
    syncDraw()
    renderAreaCircle()
    applyAreaResults()
    applyAreaCursor()
    emitBounds()
  })
  map.on('moveend', scheduleAttributionUpdate)
  map.on('moveend', emitBounds)
})

watch(basemap, (id) => {
  void applyBasemap(id)
})

watch([vacantOnly, useClasses], () => {
  if (!map?.getLayer('parcels-fill')) return
  map.setFilter('parcels-fill', parcelFilter())
  map.setFilter('vacant-markers', markerFilter())
})

watch(colorMode, () => {
  applyFillPaint()
  applyMarkerIcon()
})

watch([detail, show3d], () => {
  if (show3d.value && detail.value !== null) {
    void parcelStore.loadEnvelope()
  }
  renderEnvelope()
  applyPitch()
})

watch(envelope, () => {
  renderEnvelope()
  applyPitch()
})

watch(assemblage, () => {
  applyAssemblage()
})

watch(detail, () => focusSelected())

watch([areaActive, areaShape, areaCenter, areaRadius], () => {
  syncDraw()
  renderAreaCircle()
  applyAreaCursor()
})

watch(areaResults, () => applyAreaResults())

onBeforeUnmount(() => {
  if (attributionTimer) clearTimeout(attributionTimer)
  if (draw && drawStarted) draw.stop()
  popup.remove()
  map?.remove()
})
</script>

<template>
  <div ref="container" class="map-root" />
  <div v-if="envelopeCaption" class="envelope-caption">
    <q-icon name="deployed_code" size="16px" class="q-mr-xs" />
    <span>{{ envelopeCaption }}</span>
    <span class="ec-note">approx · informational</span>
  </div>
  <div class="map-attribution">{{ attributionText }}</div>
</template>

<style scoped>
.map-root {
  position: absolute;
  inset: 0;
  min-height: 300px;
}
.envelope-caption {
  position: absolute;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: calc(100vw - 32px);
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(13, 71, 161, 0.92);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.25);
}
.envelope-caption .ec-note {
  font-weight: 400;
  font-size: 11px;
  opacity: 0.8;
  margin-left: 4px;
}
.map-attribution {
  position: absolute;
  bottom: 0;
  right: 0;
  z-index: 4;
  max-width: 70vw;
  padding: 1px 6px;
  border-radius: 4px 0 0 0;
  background: rgba(255, 255, 255, 0.75);
  color: #455a64;
  font-size: 10px;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
