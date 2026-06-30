<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, ref } from 'vue'

import AppHeader from '@/components/AppHeader.vue'
import AreaSearchPanel from '@/components/AreaSearchPanel.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import MapView from '@/components/MapView.vue'
import ParcelPanel from '@/components/ParcelPanel.vue'
import SearchBox from '@/components/SearchBox.vue'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const $q = useQuasar()
const drawerOpen = ref(!$q.screen.lt.md)
const drawerWidth = computed(() => ($q.screen.lt.sm ? Math.min($q.screen.width - 36, 380) : 430))

function onSelect(parcelNumber: string): void {
  void store.select(parcelNumber)
  if ($q.screen.lt.md) drawerOpen.value = true
}
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <AppHeader>
      <template #lead>
        <q-btn
          flat
          dense
          round
          icon="menu"
          class="lt-md"
          aria-label="Toggle panel"
          @click="drawerOpen = !drawerOpen"
        />
      </template>
    </AppHeader>

    <q-drawer
      v-model="drawerOpen"
      :width="drawerWidth"
      show-if-above
      bordered
      side="left"
      :breakpoint="1023"
    >
      <div class="column no-wrap fit drawer-shell">
        <div class="q-pa-sm search-strip">
          <SearchBox @select="onSelect" />
        </div>
        <q-separator />
        <ParcelPanel class="col" />
      </div>
    </q-drawer>

    <q-page-container>
      <q-page class="map-page">
        <MapView @select="onSelect" />
        <FilterPanel />
        <AreaSearchPanel @select="onSelect" />
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.map-page {
  position: relative;
  height: calc(100vh - 54px);
  height: calc(100dvh - 54px);
  overflow: hidden;
}
.drawer-shell {
  background: var(--lot-surface);
}
.search-strip {
  background: var(--lot-surface-2);
}
</style>
