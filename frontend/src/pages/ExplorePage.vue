<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BuyBoxPanel from '@/components/BuyBoxPanel.vue'
import MapControlsOverlay from '@/components/MapControlsOverlay.vue'
import MapView from '@/components/MapView.vue'
import ParcelDossier from '@/components/ParcelDossier.vue'
import {
  DEFAULT_VIEW_MODE,
  boundsToPolygon,
  canListViewport,
  exploreQuery,
  type MapBounds,
  readExploreState,
} from '@/lib/explore'
import { useAreaSearchStore } from '@/stores/areaSearch'
import { USE_CLASS_OPTIONS, type UseClass, useFiltersStore } from '@/stores/filters'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { detail } = storeToRefs(store)
const areaSearch = useAreaSearchStore()
const {
  results: areaResults,
  loading: areaLoading,
  active: areaActive,
  shape: areaShape,
  minScore,
  total: areaTotal,
  truncated: areaTruncated,
} = storeToRefs(areaSearch)
const filters = useFiltersStore()
const { activeCount: buyBoxCount, vacantOnly, useClasses } = storeToRefs(filters)
const $q = useQuasar()
const route = useRoute()
const router = useRouter()

const VALID_CLASSES = USE_CLASS_OPTIONS.map((option) => option.value)
const initialState = readExploreState(route.query)
areaShape.value = initialState.shape
vacantOnly.value = initialState.vacantOnly
useClasses.value = initialState.useClasses.filter((value): value is UseClass =>
  VALID_CLASSES.includes(value as UseClass),
)
minScore.value = initialState.minScore

const hasResults = computed(() => areaResults.value.length > 0)

watch([areaShape, vacantOnly, useClasses, minScore], () => {
  void router.replace({
    query: exploreQuery({
      view: DEFAULT_VIEW_MODE,
      shape: areaShape.value,
      vacantOnly: vacantOnly.value,
      useClasses: [...useClasses.value],
      minScore: minScore.value,
    }),
  })
})

const VIEWPORT_DEBOUNCE_MS = 350
const belowZoom = ref(true)
const lastBounds = ref<MapBounds | null>(null)
let boundsTimer: ReturnType<typeof setTimeout> | undefined

function runViewport(): void {
  if (areaActive.value || belowZoom.value || lastBounds.value === null) return
  void areaSearch.searchViewport(boundsToPolygon(lastBounds.value))
}

function onBounds(bounds: MapBounds): void {
  lastBounds.value = bounds
  belowZoom.value = !canListViewport(bounds.zoom)
  if (boundsTimer) clearTimeout(boundsTimer)
  boundsTimer = setTimeout(() => {
    if (areaActive.value) return
    if (belowZoom.value) areaSearch.clearResults()
    else runViewport()
  }, VIEWPORT_DEBOUNCE_MS)
}

watch(areaActive, (active) => {
  if (!active) runViewport()
})

const buyBoxKey = computed(() =>
  JSON.stringify([
    filters.vacantOnly,
    [...filters.useClasses],
    areaSearch.minValue,
    areaSearch.maxValue,
    areaSearch.minLotArea,
    areaSearch.maxLotArea,
    areaSearch.minScore,
  ]),
)
let criteriaTimer: ReturnType<typeof setTimeout> | undefined

watch(buyBoxKey, () => {
  if (criteriaTimer) clearTimeout(criteriaTimer)
  criteriaTimer = setTimeout(() => {
    if (areaActive.value) void areaSearch.rerun()
    else runViewport()
  }, VIEWPORT_DEBOUNCE_MS)
})

onBeforeUnmount(() => {
  if (boundsTimer) clearTimeout(boundsTimer)
  if (criteriaTimer) clearTimeout(criteriaTimer)
})

const isMobile = computed(() => $q.screen.lt.md)
const filtersOpen = ref(false)

const toolbarLabel = computed(() => {
  const total = areaTotal.value
  if (total === 0) return 'Explore vacant lots'
  const base = `${total.toLocaleString()} lot${total === 1 ? '' : 's'} in view`
  return areaTruncated.value ? `${base} · showing top ${areaResults.value.length} by score` : base
})

function onSelect(parcelNumber: string): void {
  if (isMobile.value) {
    void router.push({ name: 'parcel', params: { market: route.params.market, id: parcelNumber } })
    return
  }
  void store.select(parcelNumber)
}
</script>

<template>
  <q-layout view="hHh lpR fFf" container class="explore-layout">
    <q-page-container>
      <div class="explore-body">
        <div class="explore-toolbar">
          <span class="toolbar-count lot-numeric">{{ toolbarLabel }}</span>
          <q-space />
          <q-btn
            outline
            no-caps
            dense
            color="grey-8"
            icon="tune"
            label="Filters"
            class="filters-btn"
            @click="filtersOpen = true"
          >
            <q-badge v-if="buyBoxCount > 0" color="primary" rounded floating>{{
              buyBoxCount
            }}</q-badge>
          </q-btn>
        </div>

        <div class="explore-split">
          <section class="map-pane">
            <MapView @select="onSelect" @boundschange="onBounds" />
            <MapControlsOverlay />
            <div v-if="!hasResults && !areaActive && !areaLoading" class="map-hint">
              <q-icon :name="belowZoom ? 'zoom_in' : 'search_off'" size="15px" class="q-mr-xs" />
              {{ belowZoom ? 'Zoom in to list lots in view' : 'No lots in this view' }}
            </div>
          </section>

          <section v-if="!isMobile" class="dossier-pane column no-wrap dossier-shell">
            <ParcelDossier v-if="detail" class="col" />
            <div v-else class="dossier-empty">
              <q-icon name="ads_click" size="36px" color="grey-4" />
              <div class="empty-title">Select a lot</div>
              <div class="empty-sub">
                Click a lot on the map, or search above, to see its verdict, deal math, land, and
                risk.
              </div>
            </div>
          </section>
        </div>
      </div>
    </q-page-container>

    <q-drawer
      v-model="filtersOpen"
      side="left"
      overlay
      bordered
      :width="340"
      class="filters-drawer"
    >
      <div class="column no-wrap fit">
        <div class="filters-head">
          <q-icon name="tune" size="18px" class="q-mr-sm" />
          <span class="filters-title">Filters</span>
          <q-badge v-if="buyBoxCount > 0" color="primary" class="q-ml-sm">{{ buyBoxCount }}</q-badge>
          <q-space />
          <q-btn
            flat
            dense
            round
            size="sm"
            icon="close"
            aria-label="Close filters"
            @click="filtersOpen = false"
          />
        </div>
        <q-scroll-area class="col">
          <div class="q-pa-md">
            <BuyBoxPanel />
          </div>
        </q-scroll-area>
      </div>
    </q-drawer>
  </q-layout>
</template>

<style scoped>
.explore-layout {
  height: calc(100vh - 54px - var(--lot-footer-h, 0px));
  height: calc(100dvh - 54px - var(--lot-footer-h, 0px));
}
.explore-body {
  height: calc(100vh - 54px - var(--lot-footer-h, 0px));
  height: calc(100dvh - 54px - var(--lot-footer-h, 0px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--lot-bg);
}
.explore-toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--lot-surface);
  border-bottom: 1px solid var(--lot-border);
}
.toolbar-count {
  font-size: 14px;
  font-weight: 600;
  color: var(--lot-ink);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.filters-btn {
  flex: 0 0 auto;
}
.filters-drawer .filters-head {
  display: flex;
  align-items: center;
  padding: 12px 12px 12px 16px;
  border-bottom: 1px solid var(--lot-border);
  flex: 0 0 auto;
}
.filters-drawer .filters-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--lot-ink);
}
.explore-split {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}
.map-pane {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
}
.dossier-pane {
  flex: 0 0 clamp(400px, 32vw, 560px);
  min-height: 0;
  overflow: hidden;
  border-left: 1px solid var(--lot-border);
}
.dossier-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  padding: 40px 28px;
}
.dossier-empty .empty-title {
  font-weight: 700;
  color: var(--lot-ink);
}
.dossier-empty .empty-sub {
  font-size: 13px;
  line-height: 1.4;
  color: var(--lot-muted);
  max-width: 300px;
}
.map-hint {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  display: flex;
  align-items: center;
  max-width: calc(100% - 24px);
  padding: 6px 12px;
  border-radius: var(--lot-radius-pill);
  background: var(--lot-surface);
  border: 1px solid var(--lot-border);
  box-shadow: var(--lot-shadow-sm);
  color: var(--lot-muted);
  font-size: 12.5px;
  font-weight: 500;
  white-space: nowrap;
}
.dossier-shell {
  background: var(--lot-surface);
}
</style>
