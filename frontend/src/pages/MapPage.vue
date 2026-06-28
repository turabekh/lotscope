<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'

import AuthDialog from '@/components/AuthDialog.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import MapView from '@/components/MapView.vue'
import ParcelPanel from '@/components/ParcelPanel.vue'
import SearchBox from '@/components/SearchBox.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useAuthStore } from '@/stores/auth'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const auth = useAuthStore()
const $q = useQuasar()
const drawerOpen = ref(!$q.screen.lt.md)
const drawerWidth = computed(() => ($q.screen.lt.sm ? Math.min($q.screen.width - 36, 380) : 430))

onMounted(() => {
  void auth.restore()
})

function onSelect(parcelNumber: string): void {
  void store.select(parcelNumber)
  if ($q.screen.lt.md) drawerOpen.value = true
}
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn
          flat
          dense
          round
          icon="menu"
          class="lt-md q-mr-xs"
          aria-label="Toggle panel"
          @click="drawerOpen = !drawerOpen"
        />
        <q-icon name="location_city" size="26px" class="q-mr-sm" />
        <q-toolbar-title>
          LotScope <span class="text-weight-light">PHL</span>
        </q-toolbar-title>
        <q-chip dense outline color="white" text-color="white" class="gt-sm q-mr-sm">
          Philadelphia parcel intelligence
        </q-chip>
        <UserMenu />
      </q-toolbar>
    </q-header>

    <AuthDialog />

    <q-drawer
      v-model="drawerOpen"
      :width="drawerWidth"
      show-if-above
      bordered
      side="left"
      :breakpoint="1023"
    >
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
