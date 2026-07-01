<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import ParcelDossier from '@/components/ParcelDossier.vue'
import { useParcelStore } from '@/stores/parcel'

const route = useRoute()
const store = useParcelStore()

function load(): void {
  const id = route.params.id
  if (typeof id === 'string' && id !== '') void store.select(id)
}

onMounted(load)
watch(() => route.params.id, load)
</script>

<template>
  <div class="dossier-page">
    <div class="dossier-frame">
      <ParcelDossier />
    </div>
  </div>
</template>

<style scoped>
.dossier-page {
  height: calc(100vh - 54px);
  height: calc(100dvh - 54px);
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
</style>
