<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BuyBoxPanel from '@/components/BuyBoxPanel.vue'
import ExploreResultsList from '@/components/ExploreResultsList.vue'
import MapControlsOverlay from '@/components/MapControlsOverlay.vue'
import MapView from '@/components/MapView.vue'
import ParcelDossier from '@/components/ParcelDossier.vue'
import {
  boundsToPolygon,
  canListViewport,
  exploreQuery,
  type ExploreViewMode,
  type MapBounds,
  paneVisibility,
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

const viewMode = ref<ExploreViewMode>(initialState.view)
const panes = computed(() => paneVisibility(viewMode.value))
const hasResults = computed(() => areaResults.value.length > 0)
const showList = computed(() => panes.value.list && hasResults.value)
const showMap = computed(() => panes.value.map || !hasResults.value)

watch([viewMode, areaShape, vacantOnly, useClasses, minScore], () => {
  void router.replace({
    query: exploreQuery({
      view: viewMode.value,
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

const VIEW_OPTIONS: { label: string; value: ExploreViewMode; icon: string }[] = [
  { label: 'List', value: 'list', icon: 'view_list' },
  { label: 'Split', value: 'split', icon: 'vertical_split' },
  { label: 'Map', value: 'map', icon: 'map' },
]

const toolbarLabel = computed(() => {
  const total = areaTotal.value
  if (total === 0) return 'Explore vacant lots'
  const base = `${total.toLocaleString()} lot${total === 1 ? '' : 's'} in view`
  return areaTruncated.value ? `${base} · showing top ${areaResults.value.length} by score` : base
})

const drawerOpen = ref(false)
const drawerWidth = computed(() => ($q.screen.lt.sm ? Math.min($q.screen.width - 36, 380) : 430))

function onSelect(parcelNumber: string): void {
  void store.select(parcelNumber)
  drawerOpen.value = true
}
</script>

<template>
  <q-layout view="hHh lpR fFf" container class="explore-layout">
    <q-page-container>
      <div class="explore-body">
        <div class="explore-toolbar">
          <span class="toolbar-count lot-numeric">{{ toolbarLabel }}</span>
          <q-btn
            outline
            no-caps
            dense
            color="grey-8"
            icon-right="expand_more"
            label="Buy box"
            class="buy-box-btn"
          >
            <q-badge v-if="buyBoxCount > 0" color="primary" rounded floating>{{
              buyBoxCount
            }}</q-badge>
            <q-menu anchor="bottom left" self="top left">
              <BuyBoxPanel />
            </q-menu>
          </q-btn>
          <q-space />
          <q-btn-toggle
            v-model="viewMode"
            :options="VIEW_OPTIONS"
            no-caps
            dense
            unelevated
            rounded
            toggle-color="primary"
            color="grey-2"
            text-color="grey-9"
            class="view-toggle"
          />
        </div>

        <div class="explore-split">
          <section v-show="showList" class="list-pane" :class="{ rail: viewMode === 'split' }">
            <ExploreResultsList
              :results="areaResults"
              :selected-parcel="detail?.parcel_number ?? null"
              :loading="areaLoading"
              @select="onSelect"
            />
          </section>

          <section v-show="showMap" class="map-pane">
            <MapView @select="onSelect" @boundschange="onBounds" />
            <MapControlsOverlay />
            <div v-if="!hasResults && !areaActive && !areaLoading" class="map-hint">
              <q-icon :name="belowZoom ? 'zoom_in' : 'search_off'" size="15px" class="q-mr-xs" />
              {{ belowZoom ? 'Zoom in to list lots in view' : 'No lots in this view' }}
            </div>
          </section>
        </div>
      </div>
    </q-page-container>

    <q-drawer v-model="drawerOpen" side="right" overlay bordered :width="drawerWidth">
      <div class="column no-wrap fit dossier-shell">
        <ParcelDossier class="col" />
      </div>
    </q-drawer>
  </q-layout>
</template>

<style scoped>
.explore-layout {
  height: calc(100vh - 54px);
  height: calc(100dvh - 54px);
}
.explore-body {
  height: calc(100vh - 54px);
  height: calc(100dvh - 54px);
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
}
.view-toggle {
  font-size: 12px;
}
.explore-split {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}
.list-pane {
  flex: 1;
  min-width: 0;
}
.list-pane.rail {
  flex: 0 0 360px;
  max-width: 360px;
  border-right: 1px solid var(--lot-border);
}
.map-pane {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
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
