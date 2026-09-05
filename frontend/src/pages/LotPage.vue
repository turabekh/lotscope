<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MapView from '@/components/MapView.vue'
import ParcelDossier from '@/components/ParcelDossier.vue'
import { useParcelStore } from '@/stores/parcel'

const route = useRoute()
const router = useRouter()
const store = useParcelStore()
const $q = useQuasar()

const isMobile = computed(() => $q.screen.lt.md)

function load(): void {
  const id = route.params.parcelNumber
  if (typeof id === 'string' && id !== '') void store.select(id)
}

function goBack(): void {
  if (window.history.length > 1) router.back()
  else void router.push({ name: 'analyst' })
}

function onSelect(parcelNumber: string): void {
  if (parcelNumber === route.params.parcelNumber) return
  void router.replace({
    name: 'lot',
    params: { parcelNumber },
  })
}

onMounted(load)
watch(() => route.params.parcelNumber, load)
</script>

<template>
  <div class="dossier-page" :class="{ mobile: isMobile }">
    <section v-if="!isMobile" class="map-pane" data-test="dossier-map">
      <MapView @select="onSelect" />
    </section>
    <div class="dossier-frame">
      <ParcelDossier :show-back="isMobile" @back="goBack" />
    </div>
  </div>
</template>

<style scoped>
.dossier-page {
  height: calc(100vh - 54px - var(--lot-footer-h, 0px));
  height: calc(100dvh - 54px - var(--lot-footer-h, 0px));
  display: flex;
  overflow: hidden;
  background: var(--lot-bg);
}
.map-pane {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
}
.dossier-frame {
  flex: 0 0 clamp(400px, 32vw, 560px);
  min-height: 0;
  overflow: hidden;
  border-left: 1px solid var(--lot-border);
  background: var(--lot-surface);
}
.dossier-page.mobile {
  flex-direction: column;
  padding: 0;
}
.dossier-page.mobile .dossier-frame {
  flex: 1;
  min-height: 0;
  border-left: none;
}
</style>
