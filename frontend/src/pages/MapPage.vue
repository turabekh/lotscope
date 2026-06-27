<script setup lang="ts">
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
        <q-toolbar-title>LotScope PHL</q-toolbar-title>
      </q-toolbar>
    </q-header>
    <q-drawer :width="400" show-if-above bordered side="left">
      <div class="q-pa-md">
        <SearchBox @select="onSelect" />
      </div>
      <q-separator />
      <ParcelPanel />
    </q-drawer>
    <q-page-container>
      <q-page class="column">
        <MapView class="col" @select="onSelect" />
      </q-page>
    </q-page-container>
  </q-layout>
</template>
