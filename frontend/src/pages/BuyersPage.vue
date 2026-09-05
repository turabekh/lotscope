<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { BuyerRoster, BuyerStats } from '@/lib/types'

const router = useRouter()

const SORTS = [
  { label: 'Most lot purchases', value: 'lots' },
  { label: 'Most recent', value: 'recent' },
  { label: 'Largest spend', value: 'spend' },
]

const roster = ref<BuyerRoster | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const sort = ref('lots')
const downloading = ref(false)

const sortedBuyers = computed<BuyerStats[]>(() => {
  const buyers = [...(roster.value?.buyers ?? [])]
  if (sort.value === 'recent') {
    return buyers.sort((a, b) => (b.last_purchase_at ?? '').localeCompare(a.last_purchase_at ?? ''))
  }
  if (sort.value === 'spend') {
    return buyers.sort((a, b) => (b.total_consideration ?? 0) - (a.total_consideration ?? 0))
  }
  return buyers.sort((a, b) => b.lot_purchases_window - a.lot_purchases_window)
})

function money(value: number | null): string {
  return value === null ? '—' : `$${Math.round(value).toLocaleString()}`
}

function when(value: string | null): string {
  return value
    ? new Date(value).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
    : '—'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    roster.value = await api.getBuyers()
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load buyers.'
  } finally {
    loading.value = false
  }
}

async function exportCsv(): Promise<void> {
  downloading.value = true
  try {
    await api.downloadBuyersCsv()
  } finally {
    downloading.value = false
  }
}

function openBuyer(buyer: BuyerStats): void {
  void router.push({
    name: 'buyer-profile',
    params: { buyerKey: buyer.buyer_key },
  })
}

onMounted(load)
</script>

<template>
  <q-page class="q-pa-md">
    <div class="buyers-wrap">
      <div class="row items-center justify-between q-mb-md">
        <div>
          <div class="text-h6">Active lot buyers</div>
          <div class="text-caption text-grey-7">
            Entities with 3+ arm's-length vacant-lot purchases in the last 24 months.
          </div>
        </div>
        <q-btn
          v-if="roster?.available && roster.buyers.length"
          outline
          no-caps
          color="primary"
          icon="download"
          label="Export CSV"
          :loading="downloading"
          @click="exportCsv"
        />
      </div>

      <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
        {{ error }}
      </q-banner>

      <q-inner-loading :showing="loading" color="primary" />

      <div v-if="roster && !roster.available" class="empty">
        <q-icon name="lock" size="40px" color="grey-5" />
        <div class="text-body1 q-mt-sm">{{ roster.note }}</div>
      </div>

      <template v-if="roster">
        <div class="row items-center q-mb-sm">
          <q-select
            v-model="sort"
            outlined
            dense
            emit-value
            map-options
            :options="SORTS"
            style="min-width: 200px"
          />
          <q-space />
          <div class="text-caption text-grey-6">{{ roster.total }} active buyers</div>
        </div>

        <q-markup-table v-if="sortedBuyers.length" flat bordered class="buyers-table">
          <thead>
            <tr>
              <th class="text-left">Entity</th>
              <th class="text-right">Lots (24mo)</th>
              <th class="text-right">All purchases</th>
              <th class="text-right">Median lot</th>
              <th class="text-left">Last buy</th>
              <th class="text-left">Mailing</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="buyer in sortedBuyers"
              :key="buyer.buyer_key"
              v-ripple
              class="buyer-row"
              @click="openBuyer(buyer)"
            >
              <td class="text-left">{{ buyer.display_name }}</td>
              <td class="text-right">{{ buyer.lot_purchases_window }}</td>
              <td class="text-right">{{ buyer.purchases_window }}</td>
              <td class="text-right">{{ money(buyer.median_price) }}</td>
              <td class="text-left">{{ when(buyer.last_purchase_at) }}</td>
              <td class="text-left ellipsis">{{ buyer.mailing_address ?? '—' }}</td>
            </tr>
          </tbody>
        </q-markup-table>

        <div v-else-if="!loading" class="empty">
          <q-icon name="search_off" size="40px" color="grey-5" />
          <div class="text-body1 q-mt-sm">No active lot buyers loaded for this market yet.</div>
        </div>
      </template>
    </div>
  </q-page>
</template>

<style scoped>
.buyers-wrap {
  max-width: 1000px;
  margin: 0 auto;
  position: relative;
}
.buyer-row {
  cursor: pointer;
}
.upgrade,
.empty {
  text-align: center;
  padding: 56px 20px;
}
</style>
