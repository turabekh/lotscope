<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { ParcelCompareItem } from '@/lib/types'
import { useCompareStore } from '@/stores/compare'
import { useParcelStore } from '@/stores/parcel'

const router = useRouter()
const compare = useCompareStore()
const parcelStore = useParcelStore()

const items = ref<ParcelCompareItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

function money(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value < 0 ? '-' : ''
  return `${sign}$${Math.abs(Math.round(value)).toLocaleString('en-US')}`
}

function num(value: number | null | undefined, suffix = ''): string {
  return value == null ? '—' : `${Math.round(value).toLocaleString('en-US')}${suffix}`
}

function pct(value: number | null | undefined): string {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function yesNo(value: boolean | null | undefined): string {
  if (value == null) return '—'
  return value ? 'Yes' : 'No'
}

interface Row {
  label: string
  value: (item: ParcelCompareItem) => string
  emphasis?: boolean
}

const ROWS: Row[] = [
  { label: 'Zoning', value: (i) => i.detail.base_zoning_code ?? '—' },
  { label: 'Vacant', value: (i) => yesNo(i.detail.is_vacant) },
  { label: 'Lot area', value: (i) => num(i.detail.lot_area_sqft, ' sq ft') },
  {
    label: 'Frontage × depth',
    value: (i) => `${num(i.detail.frontage_ft)} × ${num(i.detail.depth_ft)} ft`,
  },
  { label: 'Assessed value', value: (i) => money(i.detail.market_value) },
  { label: 'Opportunity score', value: (i) => num(i.verdict?.opportunity_score), emphasis: true },
  { label: 'Buildability', value: (i) => num(i.verdict?.buildability_score) },
  { label: 'By-right units', value: (i) => num(i.verdict?.by_right_units) },
  { label: 'Max height', value: (i) => num(i.verdict?.max_height_ft, ' ft') },
  {
    label: 'Est. land value',
    value: (i) =>
      i.verdict?.value_estimate_low != null
        ? `${money(i.verdict.value_estimate_low)} – ${money(i.verdict.value_estimate_high)}`
        : '—',
  },
  { label: 'Deal score', value: (i) => num(i.verdict?.deal_score), emphasis: true },
  { label: 'Max allowable offer', value: (i) => money(i.verdict?.max_allowable_offer) },
  { label: 'After-build value', value: (i) => money(i.verdict?.arv) },
  { label: 'Est. profit', value: (i) => money(i.verdict?.est_profit) },
  { label: 'Est. margin', value: (i) => pct(i.verdict?.est_margin) },
  { label: 'Underpriced', value: (i) => yesNo(i.verdict?.is_underpriced) },
  { label: 'Risk score', value: (i) => num(i.verdict?.risk_score) },
  { label: 'Risk flags', value: (i) => String(i.verdict?.risk_flags.length ?? 0) },
]

async function load(): Promise<void> {
  if (compare.parcelNumbers.length < 2) {
    items.value = []
    return
  }
  loading.value = true
  error.value = null
  try {
    const response = await api.compareParcels(compare.parcelNumbers)
    items.value = response.items
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load comparison.'
  } finally {
    loading.value = false
  }
}

function openParcel(parcelNumber: string): void {
  void parcelStore.select(parcelNumber)
  void router.push('/app')
}

function removeParcel(parcelNumber: string): void {
  compare.remove(parcelNumber)
}

watch(() => [...compare.parcelNumbers], load, { immediate: true })
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat dense round icon="arrow_back" to="/app" aria-label="Back to map" />
        <q-toolbar-title>Compare parcels</q-toolbar-title>
        <q-btn
          v-if="compare.count > 0"
          flat
          dense
          no-caps
          icon="clear_all"
          label="Clear"
          @click="compare.clear()"
        />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="q-pa-md">
        <div class="compare-wrap">
          <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
            {{ error }}
          </q-banner>

          <q-inner-loading :showing="loading" color="primary" />

          <div v-if="compare.count < 2 && !loading" class="empty">
            <q-icon name="compare_arrows" size="52px" color="grey-4" />
            <div class="text-subtitle1 text-grey-7 q-mt-md">Pick at least two lots to compare</div>
            <div class="text-body2 text-grey-6">
              Open any parcel on the map and tap “Compare” to add it here (up to four).
            </div>
            <q-btn class="q-mt-md" unelevated no-caps color="primary" icon="map" label="Go to map" to="/app" />
          </div>

          <q-markup-table v-else-if="items.length" flat bordered separator="cell" class="compare-table">
            <thead>
              <tr>
                <th class="metric-col"></th>
                <th v-for="item in items" :key="item.detail.parcel_number" class="parcel-head">
                  <div class="addr ellipsis" @click="openParcel(item.detail.parcel_number)">
                    {{ item.detail.address ?? item.detail.parcel_number }}
                  </div>
                  <div class="pn">{{ item.detail.parcel_number }}</div>
                  <q-btn
                    flat
                    dense
                    round
                    size="xs"
                    icon="close"
                    color="grey-6"
                    :aria-label="`Remove ${item.detail.parcel_number}`"
                    @click="removeParcel(item.detail.parcel_number)"
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in ROWS" :key="row.label" :class="{ emphasis: row.emphasis }">
                <td class="metric-col">{{ row.label }}</td>
                <td
                  v-for="item in items"
                  :key="item.detail.parcel_number"
                  class="text-right value-cell"
                >
                  {{ row.value(item) }}
                </td>
              </tr>
            </tbody>
          </q-markup-table>

          <div class="text-caption text-grey-5 q-mt-md">
            Informational only — estimates from public city data and modeled assumptions, not advice.
          </div>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.compare-wrap {
  max-width: 980px;
  margin: 0 auto;
  position: relative;
}
.compare-table {
  border-radius: var(--lot-radius);
}
.metric-col {
  text-align: left;
  font-weight: 600;
  color: var(--lot-muted);
  white-space: nowrap;
  background: #f7f9fc;
  position: sticky;
  left: 0;
}
.parcel-head {
  text-align: right;
  min-width: 150px;
  vertical-align: top;
}
.parcel-head .addr {
  font-weight: 700;
  color: var(--lot-ink);
  cursor: pointer;
}
.parcel-head .addr:hover {
  text-decoration: underline;
}
.parcel-head .pn {
  font-size: 11px;
  color: var(--lot-muted);
}
.value-cell {
  font-variant-numeric: tabular-nums;
}
tr.emphasis td {
  font-weight: 700;
  background: #eef4ff;
  color: var(--lot-ink);
}
.empty {
  text-align: center;
  padding: 56px 20px;
}
</style>
