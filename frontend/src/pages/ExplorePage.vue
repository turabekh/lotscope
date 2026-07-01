<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AreaSearchPanel from '@/components/AreaSearchPanel.vue'
import ExploreResultsList from '@/components/ExploreResultsList.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import MapView from '@/components/MapView.vue'
import ParcelPanel from '@/components/ParcelPanel.vue'
import {
  DEFAULT_VIEW_MODE,
  type ExploreViewMode,
  paneVisibility,
  readViewMode,
} from '@/lib/explore'
import { useAreaSearchStore } from '@/stores/areaSearch'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { detail } = storeToRefs(store)
const areaSearch = useAreaSearchStore()
const { results: areaResults, loading: areaLoading } = storeToRefs(areaSearch)
const $q = useQuasar()
const route = useRoute()
const router = useRouter()

const viewMode = ref<ExploreViewMode>(readViewMode(route.query.view))
const panes = computed(() => paneVisibility(viewMode.value))

watch(viewMode, (mode) => {
  const query = { ...route.query }
  if (mode === DEFAULT_VIEW_MODE) delete query.view
  else query.view = mode
  void router.replace({ query })
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
          <section v-show="panes.list" class="list-pane">
            <ExploreResultsList
              :results="areaResults"
              :selected-parcel="detail?.parcel_number ?? null"
              :loading="areaLoading"
              @select="onSelect"
            />
          </section>

          <section v-show="panes.map" class="map-pane">
            <MapView @select="onSelect" />
            <FilterPanel />
            <AreaSearchPanel />
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
}
.list-pane {
  flex: 1;
  min-width: 0;
  border-right: 1px solid var(--lot-border);
}
.map-pane {
  flex: 1.2;
  min-width: 0;
  position: relative;
}
.dossier-shell {
  background: var(--lot-surface);
}
</style>
