<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '@/lib/api'
import type { ParcelSummaryResult } from '@/lib/types'

const props = defineProps<{ parcelNumber: string }>()

const summary = ref<ParcelSummaryResult | null>(null)
const loading = ref(false)
let requestToken = 0

const COVERAGE_COLOR: Record<string, string> = {
  high: 'positive',
  medium: 'blue-grey-6',
  low: 'grey-6',
}

async function load(): Promise<void> {
  const token = ++requestToken
  const parcelNumber = props.parcelNumber
  summary.value = null
  loading.value = true
  try {
    const result = await api.getParcelSummary(parcelNumber)
    if (token === requestToken && result.parcel_number === props.parcelNumber) {
      summary.value = result
    }
  } catch {
    if (token === requestToken) summary.value = null
  } finally {
    if (token === requestToken) loading.value = false
  }
}

onMounted(load)
watch(() => props.parcelNumber, load)
</script>

<template>
  <!-- Collapsed by default. The verdict section above already states the finding, and the
       Analyst answers follow-ups on the same screen; this is the plain-words read plus the
       one thing nothing else shows, which is how much of the lot we actually hold data for. -->
  <q-expansion-item
    v-if="summary"
    dense
    label="In plain words"
    class="snapshot rounded-borders"
    data-test="lot-plain-words"
  >
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-space />
        <q-chip
          dense
          square
          :color="COVERAGE_COLOR[summary.data_coverage] ?? 'grey-6'"
          text-color="white"
        >
          {{ summary.data_coverage }} data coverage
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Share of core dimensions — verdict, land-value comps, assessment — with data for this
            parcel. Not a claim about how accurate the estimate is.
          </q-tooltip>
        </q-chip>
      </div>
      <div class="text-body2 q-mt-xs">{{ summary.summary }}</div>
      <div class="text-caption lot-text-faint q-mt-sm snapshot-foot">
        AI-generated from LotScope's computed data · informational, not legal or financial advice.
        <span class="snapshot-prov lot-numeric">Parcel {{ summary.parcel_number }}</span>
      </div>
    </q-card-section>
  </q-expansion-item>
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
.snapshot-foot {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.snapshot-prov {
  color: var(--lot-faint);
}
</style>
