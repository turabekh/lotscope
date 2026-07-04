<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { NeighborhoodMarketResponse, NeighborhoodMarketStats } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'

const router = useRouter()
const market = useMarketStore()
const { user } = storeToRefs(useAuthStore())

const PAID_TIERS = ['pro', 'investor', 'enterprise']
const hasAccess = computed(() => PAID_TIERS.includes(user.value?.tier ?? 'free'))

const data = ref<NeighborhoodMarketResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

type SortKey = keyof Omit<NeighborhoodMarketStats, 'name'>
const sortKey = ref<SortKey>('vacant_lots')
const sortDir = ref<'asc' | 'desc'>('desc')

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'vacant_lots', label: 'Vacant lots' },
  { key: 'avg_distress', label: 'Avg distress' },
  { key: 'avg_opportunity', label: 'Avg opportunity' },
  { key: 'median_market_value', label: 'Median value' },
  { key: 'tax_delinquent', label: 'Delinquent' },
  { key: 'sheriff_sale', label: 'Sheriff' },
]

const rows = computed(() => {
  const list = [...(data.value?.neighborhoods ?? [])]
  const key = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return list.sort((a, b) => {
    const av = a[key] ?? -1
    const bv = b[key] ?? -1
    return av === bv ? a.name.localeCompare(b.name) : (av < bv ? -1 : 1) * dir
  })
})

const topByVacant = computed(() =>
  [...(data.value?.neighborhoods ?? [])]
    .sort((a, b) => b.vacant_lots - a.vacant_lots)
    .slice(0, 12),
)
const maxVacant = computed(() => topByVacant.value[0]?.vacant_lots ?? 0)
function barPct(value: number): string {
  return maxVacant.value > 0 ? `${(value / maxVacant.value) * 100}%` : '0%'
}

function sortBy(key: SortKey): void {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

function num(value: number | null): string {
  return value == null ? '—' : value.toLocaleString('en-US')
}

function openNeighborhood(name: string): void {
  void router.push({
    name: 'explore',
    params: { market: market.active },
    query: { neighborhood: name },
  })
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    data.value = await api.getNeighborhoodMarket()
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load market data.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (hasAccess.value) void load()
})
</script>

<template>
  <div class="market-page">
    <div class="head">
      <div class="text-h5 text-weight-bold">Market intelligence</div>
      <div class="text-body2 text-grey-7">
        Where Philadelphia's vacant-land opportunity concentrates, by neighborhood.
      </div>
    </div>

    <div v-if="!hasAccess" class="upgrade">
      <q-icon name="insights" size="52px" color="grey-4" />
      <div class="text-h6 q-mt-md">Market intelligence is a Pro feature</div>
      <div class="text-body2 text-grey-7 q-mb-md">
        See vacant-lot counts, distress, and value across every Philadelphia neighborhood — so you
        know where to hunt.
      </div>
      <q-btn unelevated no-caps color="primary" label="Upgrade" :to="{ name: 'account' }" />
    </div>

    <template v-else>
      <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
        {{ error }}
      </q-banner>

      <div v-if="data" class="tiles">
        <div class="tile">
          <div class="tile-value">{{ num(data.totals.vacant_lots) }}</div>
          <div class="tile-label">Vacant lots</div>
        </div>
        <div class="tile">
          <div class="tile-value">{{ num(data.totals.neighborhoods) }}</div>
          <div class="tile-label">Neighborhoods</div>
        </div>
        <div class="tile">
          <div class="tile-value">{{ num(data.totals.tax_delinquent) }}</div>
          <div class="tile-label">Tax-delinquent</div>
        </div>
        <div class="tile">
          <div class="tile-value">{{ num(data.totals.sheriff_sale) }}</div>
          <div class="tile-label">In sheriff sale</div>
        </div>
      </div>

      <q-inner-loading :showing="loading" color="primary" />

      <section v-if="data && topByVacant.length" class="chart">
        <div class="chart-title">Top neighborhoods by vacant lots</div>
        <div class="bars">
          <div
            v-for="n in topByVacant"
            :key="n.name"
            class="bar-row"
            @click="openNeighborhood(n.name)"
          >
            <div class="bar-name">{{ n.name }}</div>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barPct(n.vacant_lots) }"></div>
            </div>
            <span class="bar-value">{{ num(n.vacant_lots) }}</span>
            <q-tooltip anchor="top middle" self="bottom middle" class="bar-tip">
              <div class="text-weight-bold">{{ n.name }}</div>
              <div>{{ num(n.vacant_lots) }} vacant lots</div>
              <div v-if="n.avg_distress != null">Avg distress {{ n.avg_distress }}</div>
              <div v-if="n.median_market_value != null">
                Median {{ formatCurrency(n.median_market_value) }}
              </div>
            </q-tooltip>
          </div>
        </div>
      </section>

      <div v-if="data" class="table-wrap">
        <table class="market-table">
          <thead>
            <tr>
              <th class="name-col">Neighborhood</th>
              <th
                v-for="col in COLUMNS"
                :key="col.key"
                class="num-col sortable"
                @click="sortBy(col.key)"
              >
                {{ col.label }}
                <q-icon
                  v-if="sortKey === col.key"
                  :name="sortDir === 'desc' ? 'arrow_drop_down' : 'arrow_drop_up'"
                  size="18px"
                />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.name"
              class="market-row"
              @click="openNeighborhood(row.name)"
            >
              <td class="name-col">{{ row.name }}</td>
              <td class="num-col strong">{{ num(row.vacant_lots) }}</td>
              <td class="num-col">{{ row.avg_distress ?? '—' }}</td>
              <td class="num-col">{{ row.avg_opportunity ?? '—' }}</td>
              <td class="num-col">
                {{ row.median_market_value == null ? '—' : formatCurrency(row.median_market_value) }}
              </td>
              <td class="num-col">{{ num(row.tax_delinquent) }}</td>
              <td class="num-col">{{ num(row.sheriff_sale) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.market-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px 16px 48px;
  position: relative;
}
.head {
  margin-bottom: 16px;
}
.upgrade {
  text-align: center;
  padding: 56px 16px;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.tile {
  border: 1px solid var(--lot-line, #e0e6f0);
  border-radius: 10px;
  padding: 14px 16px;
}
.tile-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--lot-ink);
  line-height: 1.1;
}
.tile-label {
  font-size: 12px;
  color: var(--lot-muted);
  margin-top: 2px;
}
.chart {
  border: 1px solid var(--lot-line, #e0e6f0);
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 20px;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lot-muted);
  margin-bottom: 12px;
}
.bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bar-row {
  display: grid;
  grid-template-columns: 190px 1fr auto;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.bar-name {
  font-size: 12.5px;
  color: var(--lot-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: right;
}
.bar-track {
  min-width: 0;
}
.bar-fill {
  height: 14px;
  min-width: 2px;
  border-radius: 0 4px 4px 0;
  background: var(--lot-chart-bar, #4f46e5);
  transition: width 0.3s ease;
}
.bar-row:hover .bar-fill {
  filter: brightness(1.08);
}
.bar-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--lot-muted);
  white-space: nowrap;
  text-align: right;
  min-width: 44px;
}
.bar-tip {
  font-size: 12px;
}
@media (max-width: 600px) {
  .bar-row {
    grid-template-columns: 120px 1fr;
  }
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--lot-line, #e0e6f0);
  border-radius: 10px;
}
.market-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.market-table th,
.market-table td {
  padding: 9px 12px;
  white-space: nowrap;
}
.market-table thead th {
  text-align: right;
  font-weight: 600;
  color: var(--lot-muted);
  border-bottom: 1px solid var(--lot-line, #e0e6f0);
  position: sticky;
  top: 0;
  background: var(--lot-surface, #fff);
}
.name-col {
  text-align: left !important;
}
.num-col {
  text-align: right;
}
.sortable {
  cursor: pointer;
  user-select: none;
}
.strong {
  font-weight: 700;
  color: var(--lot-ink);
}
.market-row {
  cursor: pointer;
  border-bottom: 1px solid var(--lot-line, #eef1f6);
}
.market-row:hover {
  background: var(--lot-hover, #f5f8ff);
}
</style>
