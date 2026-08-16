<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency, formatNumber, formatPercent } from '@/lib/format'
import { useParcelStore } from '@/stores/parcel'

const { marketContext } = storeToRefs(useParcelStore())

const show = computed(() => (marketContext.value?.parcels_nearby ?? 0) > 0)

interface Stat {
  label: string
  value: string
}

const stats = computed<Stat[]>(() => {
  const m = marketContext.value
  if (m === null) return []
  return [
    {
      label: 'Sales / yr',
      value: m.sales_per_year !== null ? formatNumber(m.sales_per_year) : '—',
    },
    { label: 'Median sale', value: formatCurrency(m.median_sale_price) },
    { label: 'Permits', value: formatNumber(m.permits) },
    { label: 'Vacancy', value: formatPercent(m.vacancy_rate) },
    { label: 'Median assessed', value: formatCurrency(m.median_assessed_value) },
    { label: 'Demolitions', value: formatNumber(m.demolitions) },
  ]
})
</script>

<template>
  <q-card v-if="show && marketContext" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="insights" size="18px" class="q-mr-xs" />Market context
        <q-icon name="info" size="14px" class="q-ml-xs lot-text-faint" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Recent activity within {{ formatNumber(marketContext.radius_ft) }} ft over the last
          {{ marketContext.years }} years: sales velocity, development permits, and vacancy around
          this lot. Informational.
        </q-tooltip>
        <q-space />
        <span v-if="marketContext.neighborhood" class="nbhd">{{ marketContext.neighborhood }}</span>
      </div>

      <div class="grid">
        <div v-for="stat in stats" :key="stat.label" class="tile">
          <span class="tile-label">{{ stat.label }}</span>
          <span class="tile-value">{{ stat.value }}</span>
        </div>
      </div>

      <div class="note">
        {{ formatNumber(marketContext.parcels_nearby) }} parcels within
        {{ formatNumber(marketContext.radius_ft) }} ft.
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
  margin-bottom: 8px;
}
.nbhd {
  font-size: 12px;
  font-weight: 600;
  color: var(--lot-accent-ink);
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.tile {
  display: flex;
  flex-direction: column;
  padding: 6px 8px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
}
.tile-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--lot-faint);
}
.tile-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--lot-ink);
}
.note {
  font-size: 10.5px;
  color: var(--lot-faint);
  margin-top: 6px;
}
</style>
