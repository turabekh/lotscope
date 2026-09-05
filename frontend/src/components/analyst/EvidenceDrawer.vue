<script setup lang="ts">
import { computed, watchEffect } from 'vue'

import ParcelDossier from '@/components/ParcelDossier.vue'
import { useParcelStore } from '@/stores/parcel'

const props = defineProps<{ parcelNumber: string | null; bottomSheet: boolean }>()
const emit = defineEmits<{ close: [] }>()

const store = useParcelStore()
const open = computed(() => props.parcelNumber !== null)

// The drawer shows the same Lot page the route does: one implementation, so evidence in a
// conversation and evidence on its own page can never drift apart.
function load(): void {
  if (props.parcelNumber) void store.select(props.parcelNumber)
}
watchEffect(load)
</script>

<template>
  <aside
    v-if="open"
    class="evidence"
    :class="{ 'evidence--sheet': bottomSheet }"
    data-test="evidence-drawer"
    aria-label="Evidence"
  >
    <header class="evidence__bar">
      <span class="evidence__title">{{ parcelNumber }}</span>
      <button
        type="button"
        class="evidence__close"
        data-test="evidence-close"
        @click="emit('close')"
      >
        Close
      </button>
    </header>
    <div class="evidence__body">
      <ParcelDossier />
    </div>
  </aside>
</template>

<style scoped>
.evidence {
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--ls-line, #e0e0e0);
  background: var(--ls-surface, #fff);
  height: 100%;
  overflow: hidden;
}
.evidence--sheet {
  position: fixed;
  inset: auto 0 0 0;
  height: 82vh;
  border-left: 0;
  border-top: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 10px 10px 0 0;
  box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.16);
  z-index: 2000;
}
.evidence__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
}
.evidence__title {
  font-size: 12.5px;
  color: var(--ls-muted, #6b7280);
}
.evidence__close {
  border: 0;
  background: none;
  color: var(--ls-link, #1565c0);
  font: inherit;
  font-size: 13px;
  min-height: 36px;
  padding: 0 6px;
  cursor: pointer;
}
.evidence__body {
  flex: 1;
  overflow-y: auto;
}
</style>
