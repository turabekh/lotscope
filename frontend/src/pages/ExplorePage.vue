<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AreaSearchPanel from '@/components/AreaSearchPanel.vue'
import ExploreResultsList from '@/components/ExploreResultsList.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import MapView from '@/components/MapView.vue'
import ParcelPanel from '@/components/ParcelPanel.vue'
import {
  boundsToPolygon,
  canListViewport,
  DEFAULT_VIEW_MODE,
  type ExploreViewMode,
  type MapBounds,
  paneVisibility,
  readViewMode,
} from '@/lib/explore'
import { useAreaSearchStore } from '@/stores/areaSearch'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { detail } = storeToRefs(store)
const areaSearch = useAreaSearchStore()
const { results: areaResults, loading: areaLoading, active: areaActive } = storeToRefs(areaSearch)
const $q = useQuasar()
const route = useRoute()
const router = useRouter()

const viewMode = ref<ExploreViewMode>(readViewMode(route.query.view))
const panes = computed(() => paneVisibility(viewMode.value))
const hasResults = computed(() => areaResults.value.length > 0)
const showList = computed(() => panes.value.list && hasResults.value)
const showMap = computed(() => panes.value.map || !hasResults.value)

watch(viewMode, (mode) => {
  const query = { ...route.query }
  if (mode === DEFAULT_VIEW_MODE) delete query.view
  else query.view = mode
  void router.replace({ query })
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

onBeforeUnmount(() => {
  if (boundsTimer) clearTimeout(boundsTimer)
})

const VIEW_OPTIONS: { label: string; value: ExploreViewMode; icon: string }[] = [
  { label: 'List', value: 'list', icon: 'view_list' },
  { label: 'Split', value: 'split', icon: 'vertical_split' },
  { label: 'Map', value: 'map', icon: 'map' },
]

const toolbarLabel = computed(() =>
  areaResults.value.length > 0
    ? `${areaResults.value.length} lot${areaResults.value.length === 1 ? '' : 's'} in view`
    : 'Explore vacant lots',
)

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
            <FilterPanel />
            <AreaSearchPanel />
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
        <ParcelPanel class="col" />
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
