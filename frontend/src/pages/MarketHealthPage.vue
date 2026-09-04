<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '@/lib/api'
import type { OpsMarketHealthDetail } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const isAdmin = computed(() => user.value?.role === 'admin')
const marketCode = computed(() => String(route.params.market ?? ''))

const detail = ref<OpsMarketHealthDetail | null>(null)
const loading = ref(false)
const notFound = ref(false)

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

async function load(): Promise<void> {
  if (marketCode.value === '') return
  loading.value = true
  notFound.value = false
  try {
    detail.value = await api.getOpsMarketHealth(marketCode.value)
  } catch {
    detail.value = null
    notFound.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) void load()
})

watch(marketCode, () => {
  if (isAdmin.value) void load()
})
</script>

<template>
  <q-page class="q-pa-md">
    <div v-if="!isAdmin" class="empty">
      <q-icon name="lock" size="48px" color="grey-5" />
      <div class="text-subtitle1 text-grey-7 q-mt-sm">Administrator access required</div>
    </div>

    <div v-else class="health-wrap">
      <q-inner-loading :showing="loading" color="primary" />

      <div v-if="notFound" class="empty">
        <q-icon name="help_outline" size="48px" color="grey-5" />
        <div class="text-subtitle1 text-grey-7 q-mt-sm">Market not registered</div>
      </div>

      <template v-else-if="detail">
        <div class="header-row">
          <div>
            <q-btn flat dense icon="arrow_back" :to="{ name: 'ops' }" label="Fleet" />
            <span class="text-h6 q-ml-sm">{{ detail.name }}</span>
          </div>
          <div>
            <q-badge :color="launchColor(detail.launch_status)" text-color="white">
              {{ detail.launch_status }}
            </q-badge>
            <q-badge :color="healthColor(detail.health.status)" text-color="white" class="q-ml-sm">
              data {{ detail.health.status }}
            </q-badge>
          </div>
        </div>

        <div v-if="detail.coverage_note" class="coverage-note">{{ detail.coverage_note }}</div>

        <div class="cards">
          <q-card flat bordered class="stat-card">
            <div class="stat-value">{{ count(detail.coverage.parcel_count) }}</div>
            <div class="stat-label">Parcels</div>
          </q-card>
          <q-card flat bordered class="stat-card">
            <div class="stat-value">{{ pct(detail.coverage.geometry_pct) }}</div>
            <div class="stat-label">Geometry</div>
          </q-card>
          <q-card flat bordered class="stat-card">
            <div class="stat-value">{{ pct(detail.coverage.verdict_pct) }}</div>
            <div class="stat-label">Verdicts</div>
          </q-card>
          <q-card flat bordered class="stat-card">
            <div class="stat-value">{{ pct(detail.coverage.vacant_with_comp_pct) }}</div>
            <div class="stat-label">Vacant w/ comp</div>
          </q-card>
          <q-card flat bordered class="stat-card">
            <div class="stat-value">{{ detail.zoning_standard_count.toLocaleString() }}</div>
            <div class="stat-label">
              Zoning codes ({{ detail.zoning_district_count }} districts)
            </div>
          </q-card>
        </div>

        <div class="text-subtitle2 q-mt-md q-mb-xs">Datasets</div>
        <q-markup-table flat bordered>
          <thead>
            <tr>
              <th class="text-left">Dataset</th>
              <th class="text-left">Cadence</th>
              <th class="text-left">Health</th>
              <th class="text-left">Reason</th>
              <th class="text-left">Last success</th>
              <th class="text-right">Rows</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in detail.datasets" :key="d.dataset">
              <td class="text-left">{{ d.dataset }}</td>
              <td class="text-left">{{ d.cadence }}</td>
              <td class="text-left">
                <q-badge :color="healthColor(d.freshness)" text-color="white">
                  {{ d.freshness }}
                </q-badge>
              </td>
              <td class="text-left reason">{{ d.reason }}</td>
              <td class="text-left">{{ formatTime(d.last_success_at) }}</td>
              <td class="text-right">{{ count(d.row_count) }}</td>
            </tr>
          </tbody>
        </q-markup-table>

        <div class="text-subtitle2 q-mt-md q-mb-xs">Verdict versions</div>
        <div class="versions">
          <q-badge
            v-for="v in detail.verdict_versions"
            :key="v.verdict_version ?? 'none'"
            outline
            color="primary"
            class="version-chip"
          >
            {{ v.verdict_version ?? 'no verdict' }}: {{ v.count.toLocaleString() }}
          </q-badge>
        </div>

        <div class="text-subtitle2 q-mt-md q-mb-xs">Recent jobs</div>
        <q-markup-table flat bordered>
          <thead>
            <tr>
              <th class="text-left">Job</th>
              <th class="text-left">Status</th>
              <th class="text-left">Finished</th>
              <th class="text-right">Rows</th>
              <th class="text-left">Error</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in detail.recent_jobs" :key="job.id">
              <td class="text-left">{{ job.label }}</td>
              <td class="text-left">
                <q-badge
                  :color="job.status === 'failed' ? 'negative' : 'positive'"
                  text-color="white"
                >
                  {{ job.status }}
                </q-badge>
              </td>
              <td class="text-left">{{ formatTime(job.finished_at ?? job.created_at) }}</td>
              <td class="text-right">{{ count(job.result_count) }}</td>
              <td class="text-left error-cell">{{ job.error ?? '' }}</td>
            </tr>
          </tbody>
        </q-markup-table>

        <div class="generated">As of {{ formatTime(detail.generated_at) }}</div>
      </template>
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
.health-wrap {
  position: relative;
  max-width: 1100px;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.coverage-note {
  margin: 8px 0;
  font-size: 13px;
  color: #616161;
}
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}
.stat-card {
  padding: 12px 16px;
  min-width: 140px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
}
.stat-label {
  font-size: 12px;
  color: #757575;
}
.reason {
  color: #616161;
  font-size: 13px;
}
.versions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.version-chip {
  font-size: 12px;
}
.gate-measured,
.gate-evidence {
  font-size: 13px;
  color: #616161;
  max-width: 320px;
}
.error-cell {
  color: #c10015;
  font-size: 12px;
  max-width: 280px;
}
.generated {
  margin-top: 16px;
  font-size: 12px;
  color: #757575;
}
</style>
