<script setup lang="ts">
import FilterPanel from '@/components/FilterPanel.vue'
import MapView from '@/components/MapView.vue'
import ParcelPanel from '@/components/ParcelPanel.vue'
import SearchBox from '@/components/SearchBox.vue'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()

function onSelect(parcelNumber: string): void {
  void store.select(parcelNumber)
}
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-icon name="location_city" size="26px" class="q-mr-sm" />
        <q-toolbar-title>
          LotScope <span class="text-weight-light">PHL</span>
        </q-toolbar-title>
        <q-chip dense outline color="white" text-color="white" class="gt-xs">
          Philadelphia parcel intelligence
        </q-chip>
      </q-toolbar>
    </q-header>

    <q-drawer :width="430" show-if-above bordered side="left">
      <div class="column no-wrap fit">
        <div class="q-pa-sm bg-grey-1">
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
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.map-page {
  position: relative;
  height: calc(100vh - 50px);
  height: calc(100dvh - 50px);
  overflow: hidden;
}
</style>
