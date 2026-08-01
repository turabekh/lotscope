<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ParcelDossier from '@/components/ParcelDossier.vue'
import { useParcelStore } from '@/stores/parcel'

const route = useRoute()
const router = useRouter()
const store = useParcelStore()
const $q = useQuasar()

const isMobile = computed(() => $q.screen.lt.md)

function load(): void {
  const id = route.params.id
  if (typeof id === 'string' && id !== '') void store.select(id)
}

function goBack(): void {
  if (window.history.length > 1) router.back()
  else void router.push({ name: 'explore', params: { market: route.params.market } })
}

onMounted(load)
watch(() => route.params.id, load)
</script>

<template>
  <div class="dossier-page" :class="{ mobile: isMobile }">
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
  justify-content: center;
  padding: 16px;
  overflow: hidden;
  background: var(--lot-bg);
}
.dossier-frame {
  width: 100%;
  max-width: 480px;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--lot-border);
  border-radius: var(--lot-radius);
  background: var(--lot-surface);
  box-shadow: var(--lot-shadow);
}
.dossier-page.mobile {
  flex-direction: column;
  padding: 0;
}
.dossier-page.mobile .dossier-frame {
  max-width: none;
  border: none;
  border-radius: 0;
  box-shadow: none;
  flex: 1;
  min-height: 0;
}
</style>
