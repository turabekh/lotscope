<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import { formatCurrency, scoreVar } from '@/lib/format'
import type { SpatialParcelResult } from '@/lib/types'

const props = defineProps<{
  results: SpatialParcelResult[]
  selectedParcel: string | null
  loading: boolean
}>()
const emit = defineEmits<{ select: [parcelNumber: string] }>()

const listEl = ref<HTMLElement | null>(null)

function distanceLabel(meters: number | null): string {
  if (meters === null) return ''
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`
}

watch(
  () => props.selectedParcel,
  async (parcelNumber) => {
    if (parcelNumber === null) return
    await nextTick()
    listEl.value
      ?.querySelector<HTMLElement>(`[data-parcel="${parcelNumber}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  },
)
</script>

<template>
  <div ref="listEl" class="results lot-scroll">
    <q-inner-loading :showing="loading" color="primary" />

    <template v-if="results.length">
      <button
        v-for="result in results"
        :key="result.parcel_number"
        :data-parcel="result.parcel_number"
        type="button"
        class="row"
        :class="{ active: result.parcel_number === selectedParcel }"
        @click="emit('select', result.parcel_number)"
      >
        <span class="row-main">
          <span class="row-addr ellipsis">{{ result.address ?? result.parcel_number }}</span>
          <span class="row-meta ellipsis">
            {{ result.base_zoning_code ?? '—' }}
            <span v-if="result.is_vacant" class="vac">· Vacant</span>
            <span v-if="result.market_value"> · {{ formatCurrency(result.market_value) }}</span>
            <span v-if="result.distance_m !== null" class="dist">
              · {{ distanceLabel(result.distance_m) }}</span
            >
          </span>
        </span>
        <span
          v-if="result.opportunity_score !== null"
          class="score lot-numeric"
          :style="{ background: scoreVar(result.opportunity_score) }"
        >
          {{ result.opportunity_score }}
        </span>
      </button>
    </template>

    <div v-else-if="!loading" class="empty">
      <q-icon name="travel_explore" size="30px" />
      <div class="empty-title">No lots listed yet</div>
      <div class="empty-text">Draw an area or set a buy box on the map to list parcels here.</div>
    </div>
  </div>
</template>

<style scoped>
.results {
  position: relative;
  height: 100%;
  overflow-y: auto;
  background: var(--lot-surface);
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-bottom: 1px solid var(--lot-border);
  background: transparent;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: var(--lot-ink);
}
.row:hover {
  background: var(--lot-surface-2);
}
.row.active {
  background: var(--lot-accent-soft);
  box-shadow: inset 3px 0 0 var(--lot-accent);
}
.row-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.row-addr {
  font-size: 13px;
  font-weight: 600;
}
.row-meta {
  font-size: 12px;
  color: var(--lot-muted);
}
.vac {
  color: var(--lot-sev-medium);
}
.dist {
  color: var(--lot-faint);
}
.score {
  flex: 0 0 auto;
  min-width: 26px;
  padding: 2px 6px;
  border-radius: var(--lot-radius-sm);
  color: var(--lot-on-accent);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 6px;
  padding: 56px 24px;
  color: var(--lot-faint);
}
.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--lot-muted);
}
.empty-text {
  font-size: 13px;
  max-width: 260px;
}
</style>
