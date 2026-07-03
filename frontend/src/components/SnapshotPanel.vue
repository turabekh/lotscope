<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '@/lib/api'
import type { ParcelSummaryResult } from '@/lib/types'

const props = defineProps<{ parcelNumber: string }>()

const summary = ref<ParcelSummaryResult | null>(null)
const loading = ref(false)

const CONFIDENCE_COLOR: Record<string, string> = {
  high: 'positive',
  medium: 'blue-grey-6',
  low: 'grey-6',
}

async function load(): Promise<void> {
  summary.value = null
  loading.value = true
  try {
    summary.value = await api.getParcelSummary(props.parcelNumber)
  } catch {
    summary.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.parcelNumber, load)
</script>

<template>
  <q-card v-if="summary" flat bordered class="snapshot rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="auto_awesome" size="18px" class="q-mr-xs" />Snapshot
        <q-space />
        <q-chip
          dense
          square
          :color="CONFIDENCE_COLOR[summary.confidence] ?? 'grey-6'"
          text-color="white"
        >
          {{ summary.confidence }} confidence
        </q-chip>
      </div>
      <div class="text-body2 q-mt-xs">{{ summary.summary }}</div>
      <div class="text-caption text-grey-5 q-mt-sm">
        AI-generated from LotScope's computed data · informational, not legal or financial advice.
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.snapshot {
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
</style>
