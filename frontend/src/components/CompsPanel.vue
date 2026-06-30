<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency, formatNumber, formatRange } from '@/lib/format'
import type { CompResult } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const { comps } = storeToRefs(useParcelStore())

const show = computed(() => (comps.value?.comps.length ?? 0) > 0)

const CONFIDENCE_COLOR: Record<string, string> = {
  high: 'positive',
  medium: 'amber-8',
  low: 'grey-6',
}

function rows(): CompResult[] {
  return comps.value?.comps ?? []
}

function pricePerSqft(comp: CompResult): string {
  return comp.price_per_sqft !== null ? `$${formatNumber(Math.round(comp.price_per_sqft))}/sqft` : ''
}
</script>

<template>
  <q-card v-if="show && comps" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="sell" size="18px" class="q-mr-xs" />Comparable sales
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Recorded land sales near this lot that back the value estimate. Informational; verify the
          recorded documents.
        </q-tooltip>
        <q-space />
        <q-badge :color="CONFIDENCE_COLOR[comps.confidence] ?? 'grey-6'" text-color="white">
          {{ comps.confidence }}
        </q-badge>
      </div>

      <div class="estimate">
        <span class="estimate-value">{{ formatRange(comps.low, comps.high) }}</span>
        <span class="estimate-sub">est. land value · {{ comps.comp_count }} comps</span>
      </div>

      <div class="comp-list">
        <div v-for="comp in rows()" :key="comp.parcel_number" class="comp-row">
          <div class="comp-main">
            <span class="comp-addr">{{ comp.address ?? comp.parcel_number }}</span>
            <span class="comp-meta">
              {{ formatNumber(Math.round(comp.distance_ft)) }} ft
              <template v-if="comp.sale_date"> · {{ comp.sale_date }}</template>
            </span>
          </div>
          <div class="comp-price">
            <span class="comp-amt">{{ formatCurrency(comp.sale_price) }}</span>
            <span class="comp-ppsf">{{ pricePerSqft(comp) }}</span>
          </div>
        </div>
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
.estimate {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.estimate-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--lot-ink);
}
.estimate-sub {
  font-size: 11px;
  color: var(--lot-faint);
}
.comp-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.comp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
}
.comp-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.comp-addr {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--lot-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.comp-meta {
  font-size: 10.5px;
  color: var(--lot-faint);
}
.comp-price {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  margin-left: 8px;
}
.comp-amt {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--lot-ink);
}
.comp-ppsf {
  font-size: 10.5px;
  color: var(--lot-faint);
}
</style>
