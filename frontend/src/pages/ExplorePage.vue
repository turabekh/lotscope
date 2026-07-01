<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, ref } from 'vue'

import AreaSearchPanel from '@/components/AreaSearchPanel.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import MapView from '@/components/MapView.vue'
import ParcelPanel from '@/components/ParcelPanel.vue'
import { type ExploreViewMode, paneVisibility } from '@/lib/explore'
import { useAreaSearchStore } from '@/stores/areaSearch'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const areaSearch = useAreaSearchStore()
const { results: areaResults } = storeToRefs(areaSearch)
const $q = useQuasar()

const viewMode = ref<ExploreViewMode>('split')
const panes = computed(() => paneVisibility(viewMode.value))

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
            <div v-if="areaResults.length === 0" class="list-empty">
              <q-icon name="travel_explore" size="34px" />
              <div class="list-empty-title">No lots listed yet</div>
              <div class="list-empty-text">
                Draw an area or set a buy box on the map to list parcels here.
              </div>
            </div>
            <div v-else class="list-pending">
              <q-icon name="format_list_bulleted" size="18px" class="q-mr-xs" />
              {{ areaResults.length }} lots in this area
            </div>
          </section>

          <section v-show="panes.map" class="map-pane">
            <MapView @select="onSelect" />
            <FilterPanel />
            <AreaSearchPanel @select="onSelect" />
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
  height: 100%;
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
  overflow-y: auto;
  background: var(--lot-surface);
  border-right: 1px solid var(--lot-border);
}
.map-pane {
  flex: 1.2;
  min-width: 0;
  position: relative;
}
.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 6px;
  padding: 56px 24px;
  color: var(--lot-faint);
}
.list-empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--lot-muted);
}
.list-empty-text {
  font-size: 13px;
  max-width: 260px;
}
.list-pending {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--lot-muted);
}
.dossier-shell {
  background: var(--lot-surface);
}
</style>
