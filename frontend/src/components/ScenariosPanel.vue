<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency, formatPercent } from '@/lib/format'
import type { ScenarioItem } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const { scenarios } = storeToRefs(useParcelStore())

const show = computed(() => (scenarios.value?.scenarios.length ?? 0) > 0)

function rows(): ScenarioItem[] {
  return scenarios.value?.scenarios ?? []
}

function isRecommended(item: ScenarioItem): boolean {
  return item.units === scenarios.value?.recommended_units
}

function marginClass(item: ScenarioItem): string {
  if (item.margin === null) return 'text-grey-5'
  if (item.margin >= 0.2) return 'text-positive'
  if (item.margin >= 0) return 'text-amber-8'
  return 'text-negative'
}
</script>

<template>
  <q-card v-if="show && scenarios" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="tune" size="18px" class="q-mr-xs" />Build scenarios
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Profit and margin modeled per unit count. Counts above the by-right maximum would need a
          variance. Informational; based on comp-derived ARV and default cost assumptions.
        </q-tooltip>
        <q-space />
        <q-chip
          v-if="scenarios.recommended_units"
          dense
          square
          color="primary"
          text-color="white"
          icon="star"
        >
          {{ scenarios.recommended_units }} unit(s)
        </q-chip>
      </div>

      <table class="scn">
        <thead>
          <tr>
            <th>Units</th>
            <th>Path</th>
            <th class="num">ARV</th>
            <th class="num">Profit</th>
            <th class="num">Margin</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rows()" :key="item.units" :class="{ rec: isRecommended(item) }">
            <td>
              {{ item.units }}
              <q-icon v-if="isRecommended(item)" name="star" size="12px" class="text-primary" />
            </td>
            <td>
              <span :class="item.by_right ? 'text-positive' : 'text-amber-8'">
                {{ item.by_right ? 'by-right' : 'variance' }}
              </span>
            </td>
            <td class="num">{{ formatCurrency(item.arv) }}</td>
            <td class="num">{{ formatCurrency(item.profit) }}</td>
            <td class="num" :class="marginClass(item)">{{ formatPercent(item.margin) }}</td>
          </tr>
        </tbody>
      </table>

      <div class="scn-note">{{ scenarios.confidence }} confidence · not financial advice.</div>
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
.scn {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.scn th {
  text-align: left;
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--lot-faint);
  padding: 3px 6px;
  border-bottom: 1px solid var(--lot-surface-2);
}
.scn td {
  padding: 4px 6px;
  border-bottom: 1px solid var(--lot-surface-2);
}
.scn .num {
  text-align: right;
}
.scn tr.rec td {
  background: var(--lot-accent-soft);
  font-weight: 600;
}
.scn-note {
  font-size: 10.5px;
  color: var(--lot-faint);
  margin-top: 6px;
}
</style>
