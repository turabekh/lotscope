<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/lib/api'
import type { OpsFleetOverview, OpsSheriffCoverage } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const isAdmin = computed(() => user.value?.role === 'admin')

const fleet = ref<OpsFleetOverview | null>(null)
const loading = ref(false)

function healthColor(status: string): string {
  if (status === 'green') return 'positive'
  if (status === 'amber') return 'warning'
  if (status === 'red') return 'negative'
  return 'grey'
}

function launchColor(status: string): string {
  if (status === 'live') return 'positive'
  if (status === 'pilot') return 'warning'
  return 'grey'
}

function pct(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function count(value: number | null): string {
  return value === null ? '—' : value.toLocaleString()
}

function formatTime(value: string | null): string {
  if (!value) return 'never'
  return new Date(value).toLocaleString()
}

function shortSha(value: string): string {
  return value === 'unknown' ? 'unknown' : value.slice(0, 7)
}

function openMarket(): void {
  void router.push({ name: 'ops-market' })
}

async function load(): Promise<void> {
  loading.value = true
  try {
    fleet.value = await api.getOpsFleet()
  } finally {
    loading.value = false
  }
}

const coverage = ref<OpsSheriffCoverage | null>(null)
const coverageLoading = ref(false)
const coverageError = ref<string | null>(null)

async function runCoverage(): Promise<void> {
  coverageLoading.value = true
  coverageError.value = null
  try {
    coverage.value = await api.runSheriffCoverage()
  } catch {
    coverageError.value = 'Coverage check failed — the CivilView list could not be fetched.'
  } finally {
    coverageLoading.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) void load()
})
</script>

<template>
  <q-page class="q-pa-md">
    <div v-if="!isAdmin" class="empty">
      <q-icon name="lock" size="48px" color="grey-5" />
      <div class="text-subtitle1 text-grey-7 q-mt-sm">Administrator access required</div>
    </div>

    <div v-else class="ops-wrap">
      <q-inner-loading :showing="loading" color="primary" />

      <div class="text-h6 q-mb-sm">Fleet health</div>

      <q-markup-table flat bordered class="fleet-table">
        <thead>
          <tr>
            <th class="text-left">Market</th>
            <th class="text-left">Data health</th>
            <th class="text-right">Parcels</th>
            <th class="text-right">Geometry</th>
            <th class="text-right">Verdicts</th>
            <th class="text-right">Vacant w/ comp</th>
            <th class="text-left">Last ingest</th>
            <th class="text-right">Zoning codes</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in fleet?.markets ?? []"
            :key="row.market_code"
            class="fleet-row"
            @click="openMarket()"
          >
            <td class="text-left">
              <div class="market-name">{{ row.name }}</div>
              <q-badge :color="launchColor(row.launch_status)" text-color="white" class="q-mt-xs">
                {{ row.launch_status }}
              </q-badge>
            </td>
            <td class="text-left">
              <q-badge :color="healthColor(row.health.status)" text-color="white">
                {{ row.health.status }}
              </q-badge>
              <span class="health-counts">
                {{ row.health.red }}R / {{ row.health.amber }}A / {{ row.health.green }}G
              </span>
            </td>
            <td class="text-right">{{ count(row.coverage.parcel_count) }}</td>
            <td class="text-right">{{ pct(row.coverage.geometry_pct) }}</td>
            <td class="text-right">{{ pct(row.coverage.verdict_pct) }}</td>
            <td class="text-right">{{ pct(row.coverage.vacant_with_comp_pct) }}</td>
            <td class="text-left">{{ formatTime(row.last_ingest_at) }}</td>
            <td class="text-right">{{ row.zoning_standard_count.toLocaleString() }}</td>
          </tr>
        </tbody>
      </q-markup-table>

      <div v-if="fleet" class="generated">
        As of {{ formatTime(fleet.generated_at) }}
        <span class="deployed-sha">· deployed {{ shortSha(fleet.git_sha) }}</span>
      </div>

      <div class="text-h6 q-mt-lg q-mb-sm">Sheriff-sale coverage</div>
      <q-card flat bordered class="coverage-card">
        <q-card-section class="row items-center justify-between">
          <div class="text-body2 text-grey-7">
            Reconciles the live CivilView sheriff-sale list (Philadelphia) against loaded parcels.
          </div>
          <q-btn
            color="primary"
            unelevated
            no-caps
            icon="fact_check"
            label="Run coverage check"
            :loading="coverageLoading"
            @click="runCoverage"
          />
        </q-card-section>

        <q-card-section v-if="coverageError" class="text-negative">
          {{ coverageError }}
        </q-card-section>

        <q-card-section v-else-if="coverage" class="coverage-result">
          <div class="coverage-headline">
            <span class="coverage-pct">{{ pct(coverage.coverage_pct) }}</span>
            <span class="text-grey-7">
              {{ count(coverage.reconciled) }} of {{ count(coverage.unique_parcels) }} parcels
              reconciled
            </span>
          </div>
          <div class="coverage-stats">
            <span>{{ count(coverage.total_listings) }} listings</span>
            <span>{{ count(coverage.unreconciled) }} unmatched</span>
            <span>{{ count(coverage.without_opa) }} without OPA #</span>
            <span class="text-grey-6">checked {{ formatTime(coverage.checked_at) }}</span>
          </div>
          <div v-if="coverage.sample_unreconciled.length" class="coverage-sample text-grey-7">
            Unmatched sample: {{ coverage.sample_unreconciled.join(', ') }}
          </div>
        </q-card-section>
      </q-card>
    </div>
  </q-page>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64px 0;
}
.ops-wrap {
  position: relative;
  max-width: 1100px;
}
.fleet-row {
  cursor: pointer;
}
.fleet-row:hover {
  background: rgba(0, 0, 0, 0.03);
}
.market-name {
  font-weight: 600;
}
.health-counts {
  margin-left: 8px;
  font-size: 12px;
  color: var(--q-color-grey-7, #616161);
}
.generated {
  margin-top: 12px;
  font-size: 12px;
  color: #757575;
}
.deployed-sha {
  font-family: monospace;
}
.coverage-headline {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.coverage-pct {
  font-size: 28px;
  font-weight: 600;
}
.coverage-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 8px;
  font-size: 13px;
}
.coverage-sample {
  margin-top: 8px;
  font-size: 12px;
  font-family: monospace;
}
</style>
