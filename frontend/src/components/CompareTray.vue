<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, ref } from 'vue'

import CompareTable from '@/components/CompareTable.vue'
import { MAX_COMPARE, useCompareStore } from '@/stores/compare'

const $q = useQuasar()
const compare = useCompareStore()
const { parcelNumbers, count } = storeToRefs(compare)

const expanded = ref(false)

const ready = computed(() => count.value >= 2)
const hint = computed(() => {
  if (!ready.value) return 'Add one more lot to compare them side by side'
  return 'Ready — open the side-by-side table'
})
</script>

<template>
  <div v-if="count > 0" class="compare-tray" role="region" aria-label="Compare tray">
    <div class="tray-main">
      <q-icon name="compare_arrows" size="18px" class="tray-icon" />
      <div class="tray-text">
        <div class="tray-count">{{ count }} of {{ MAX_COMPARE }} selected</div>
        <div class="tray-hint">{{ hint }}</div>
      </div>
      <q-btn
        flat
        dense
        no-caps
        size="sm"
        class="tray-clear"
        label="Clear"
        data-test="compare-clear"
        @click="compare.clear()"
      />
      <q-btn
        unelevated
        dense
        no-caps
        :color="ready ? 'primary' : 'grey-5'"
        :text-color="ready ? 'white' : 'grey-8'"
        icon="table_chart"
        label="Compare"
        :disable="!ready"
        data-test="compare-open"
        @click="expanded = true"
      />
    </div>

    <div v-if="parcelNumbers.length" class="tray-chips">
      <q-chip
        v-for="parcelNumber in parcelNumbers"
        :key="parcelNumber"
        dense
        removable
        size="sm"
        class="tray-chip"
        :label="compare.labelFor(parcelNumber)"
        :data-test="`compare-chip-${parcelNumber}`"
        @remove="compare.remove(parcelNumber)"
      />
    </div>

    <q-dialog v-model="expanded" :maximized="$q.screen.lt.sm">
      <q-card class="compare-dialog">
        <q-card-section class="row items-center q-py-sm">
          <div class="text-subtitle1 text-weight-bold">Compare lots</div>
          <q-space />
          <q-btn v-close-popup flat dense round icon="close" aria-label="Close comparison" />
        </q-card-section>
        <q-separator />
        <q-card-section class="scroll compare-dialog-body">
          <CompareTable />
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<style scoped>
.compare-tray {
  position: fixed;
  bottom: calc(16px + var(--lot-footer-h, 0px) + env(safe-area-inset-bottom));
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;
  display: block;
  width: min(560px, calc(100vw - 24px));
  padding: 10px 12px;
  background: var(--lot-surface);
  border: 1px solid var(--lot-border);
  border-radius: var(--lot-radius);
  box-shadow: var(--lot-shadow);
}
.tray-icon {
  color: var(--lot-accent);
}
.tray-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tray-text {
  min-width: 0;
  flex: 1;
}
.tray-count {
  font-weight: 700;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--lot-ink);
  white-space: nowrap;
}
.tray-hint {
  font-size: 11.5px;
  line-height: 1.35;
  color: var(--lot-muted);
}
.tray-clear {
  color: var(--lot-muted);
}
.tray-chips {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  margin-top: 8px;
  padding-bottom: 2px;
  scrollbar-width: none;
}
.tray-chips::-webkit-scrollbar {
  display: none;
}
.tray-chip {
  background: var(--lot-surface-2);
  color: var(--lot-ink);
}
.compare-dialog {
  width: 100%;
  max-width: 1000px;
  display: flex;
  flex-direction: column;
}
.compare-dialog-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  max-height: 70vh;
}
@media (max-width: 600px) {
  .compare-dialog {
    max-width: none;
    height: 100%;
  }
  .compare-dialog-body {
    max-height: none;
  }
}
</style>
