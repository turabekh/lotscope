<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const { subdivision } = storeToRefs(useParcelStore())

const overlays = computed(() => subdivision.value?.overlays ?? [])

const show = computed(() => overlays.value.length > 0)
</script>

<template>
  <q-card v-if="show" flat bordered class="rounded-borders" data-test="overlay-panel">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="layers" size="18px" class="q-mr-xs" />Zoning overlays
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Overlay districts layered on top of the base zoning. They can change dimensional standards
          such as the minimum lot area. Informational — the standards shown elsewhere on this tab
          are the base-district ones; confirm the overlay text in Title 14 §14-500.
        </q-tooltip>
        <q-space />
        <q-chip dense square color="indigo-6" text-color="white" icon="layers">
          {{ overlays.length }}
        </q-chip>
      </div>

      <div class="overlay-list">
        <q-badge
          v-for="name in overlays"
          :key="name"
          class="overlay-badge"
          outline
          color="indigo-7"
        >
          {{ name }}
        </q-badge>
      </div>

      <div class="text-caption text-grey-6 q-mt-sm">
        Overlay standards can override the base-district minimums shown above. Informational; not a
        zoning determination.
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.rounded-borders {
  border-radius: var(--lot-radius) !important;
  box-shadow: var(--lot-shadow);
}
.section-title {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 6px;
}
.overlay-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.overlay-badge {
  font-size: 11.5px;
  padding: 4px 8px;
  border-radius: var(--lot-radius-sm);
  max-width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.3;
}
</style>
