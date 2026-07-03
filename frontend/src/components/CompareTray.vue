<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import CompareTable from '@/components/CompareTable.vue'
import { MAX_COMPARE, useCompareStore } from '@/stores/compare'

const compare = useCompareStore()
const { parcelNumbers, count } = storeToRefs(compare)

const expanded = ref(false)
</script>

<template>
  <div v-if="count > 0" class="compare-tray" role="region" aria-label="Compare tray">
    <q-icon name="compare_arrows" size="20px" class="tray-icon" />
    <span class="tray-count">{{ count }} / {{ MAX_COMPARE }}</span>

    <div class="tray-chips">
      <q-chip
        v-for="parcelNumber in parcelNumbers"
        :key="parcelNumber"
        dense
        removable
        size="sm"
        color="grey-3"
        text-color="grey-9"
        :label="parcelNumber"
        @remove="compare.remove(parcelNumber)"
      />
    </div>

    <q-space />

    <q-btn
      flat
      dense
      no-caps
      size="sm"
      color="grey-7"
      label="Clear"
      icon="clear_all"
      @click="compare.clear()"
    />
    <q-btn
      unelevated
      dense
      no-caps
      color="primary"
      icon="table_chart"
      :label="`Compare (${count})`"
      :disable="count < 2"
      @click="expanded = true"
    />

    <q-dialog v-model="expanded">
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
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: min(720px, calc(100vw - 32px));
  padding: 8px 12px;
  background: var(--lot-surface);
  border: 1px solid var(--lot-border);
  border-radius: var(--lot-radius);
  box-shadow: var(--lot-shadow);
}
.tray-icon {
  color: var(--lot-accent);
}
.tray-count {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--lot-ink);
  white-space: nowrap;
}
.tray-chips {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  max-width: 340px;
}
.compare-dialog {
  width: 100%;
  max-width: 1000px;
}
.compare-dialog-body {
  max-height: 70vh;
}
</style>
