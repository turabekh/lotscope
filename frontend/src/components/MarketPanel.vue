<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency, formatNumber, formatPercent } from '@/lib/format'
import { useParcelStore } from '@/stores/parcel'

const { market } = storeToRefs(useParcelStore())

const show = computed(() => (market.value?.parcels_nearby ?? 0) > 0)

interface Stat {
  label: string
  value: string
}

const stats = computed<Stat[]>(() => {
  const m = market.value
  if (m === null) return []
  return [
    { label: 'Sales / yr', value: m.sales_per_year !== null ? formatNumber(m.sales_per_year) : '—' },
    { label: 'Median sale', value: formatCurrency(m.median_sale_price) },
    { label: 'Permits', value: formatNumber(m.permits) },
    { label: 'Vacancy', value: formatPercent(m.vacancy_rate) },
    { label: 'Median assessed', value: formatCurrency(m.median_assessed_value) },
    { label: 'Demolitions', value: formatNumber(m.demolitions) },
  ]
})
</script>

<template>
  <q-card v-if="show && market" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="insights" size="18px" class="q-mr-xs" />Market context
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Recent activity within {{ formatNumber(market.radius_ft) }} ft over the last
          {{ market.years }} years: sales velocity, development permits, and vacancy around this
          lot. Informational.
        </q-tooltip>
        <q-space />
        <span v-if="market.neighborhood" class="nbhd">{{ market.neighborhood }}</span>
      </div>

      <div class="grid">
        <div v-for="stat in stats" :key="stat.label" class="tile">
          <span class="tile-label">{{ stat.label }}</span>
          <span class="tile-value">{{ stat.value }}</span>
        </div>
      </div>

      <div class="note">
        {{ formatNumber(market.parcels_nearby) }} parcels within
        {{ formatNumber(market.radius_ft) }} ft.
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
  color: #5b6b7d;
  margin-bottom: 8px;
}
.nbhd {
  font-size: 12px;
  font-weight: 600;
  color: #2c5b8f;
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
  background: #f4f6f8;
}
.tile-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #7b8794;
}
.tile-value {
  font-size: 14px;
  font-weight: 700;
  color: #1f2933;
}
.note {
  font-size: 10.5px;
  color: #a0aab3;
  margin-top: 6px;
}
</style>
