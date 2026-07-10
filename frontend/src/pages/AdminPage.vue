<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { api } from '@/lib/api'
import type {
  AdminOverview,
  DatasetStatus,
  FetchSource,
  JobCatalogEntry,
  JobRunSummary,
  User,
} from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const $q = useQuasar()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const isAdmin = computed(() => user.value?.role === 'admin')

const overview = ref<AdminOverview | null>(null)
const datasets = ref<DatasetStatus[]>([])
const users = ref<User[]>([])
const usersTotal = ref(0)
const loading = ref(false)

const jobs = ref<JobCatalogEntry[]>([])
const jobRuns = ref<JobRunSummary[]>([])
const submittingJob = ref<string | null>(null)
const paramDialog = ref(false)
const paramJob = ref<JobCatalogEntry | null>(null)
const paramValues = ref<Record<string, string>>({})
const fetchSources = ref<FetchSource[]>([])
const fetchUrl = ref('')
const pulling = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

function fetchFilename(url: string): string {
  try {
    const path = new URL(url).pathname
    const tail = decodeURIComponent(path.slice(path.lastIndexOf('/') + 1)).trim()
    return tail || 'download'
  } catch {
    return 'download'
  }
}

async function pullSource(url: string): Promise<void> {
  if (url.trim() === '') return
  pulling.value = true
  try {
    await api.pullSource(url.trim(), fetchFilename(url.trim()))
    $q.notify({ type: 'positive', message: 'Downloaded from the server.' })
  } catch {
    $q.notify({ type: 'negative', message: 'Fetch failed — check the URL is reachable.' })
  } finally {
    pulling.value = false
  }
}

const jobGroups = computed(() => {
  const grouped = new Map<string, JobCatalogEntry[]>()
  for (const job of jobs.value) {
    const title = job.kind === 'ingest' ? `${(job.market ?? 'other').toUpperCase()} ingestion` : 'Recompute'
    const bucket = grouped.get(title) ?? []
    bucket.push(job)
    grouped.set(title, bucket)
  }
  return [...grouped.entries()].map(([title, items]) => ({ title, items }))
})

const hasActiveRun = computed(() =>
  jobRuns.value.some((run) => run.status === 'queued' || run.status === 'running'),
)

function jobIsBusy(job: JobCatalogEntry): boolean {
  if (submittingJob.value === job.id) return true
  const status = job.latest_run?.status
  return status === 'queued' || status === 'running'
}

function syncPolling(): void {
  if (hasActiveRun.value && pollTimer === null) {
    pollTimer = setInterval(() => void loadJobs(), 3000)
  } else if (!hasActiveRun.value && pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadJobs(): Promise<void> {
  jobs.value = await api.getJobCatalog()
  jobRuns.value = await api.getJobRuns(25)
  fetchSources.value = await api.getFetchSources()
  syncPolling()
}

async function runJob(job: JobCatalogEntry, params: Record<string, string> = {}): Promise<void> {
  submittingJob.value = job.id
  try {
    await api.runJob(job.id, params)
    $q.notify({ type: 'positive', message: `Queued ${job.label}.` })
    await loadJobs()
  } catch {
    $q.notify({ type: 'negative', message: `Could not start ${job.label}.` })
  } finally {
    submittingJob.value = null
  }
}

function startRun(job: JobCatalogEntry): void {
  if (job.params.length > 0) {
    paramJob.value = job
    paramValues.value = Object.fromEntries(job.params.map((param) => [param.name, '']))
    paramDialog.value = true
  } else {
    void runJob(job)
  }
}

function submitParams(): void {
  const job = paramJob.value
  if (job === null) return
  paramDialog.value = false
  void runJob(job, { ...paramValues.value })
}

const TIERS = ['free', 'pro', 'enterprise']
const ROLES = ['user', 'admin']

const overviewCards = computed(() => {
  const o = overview.value
  if (o === null) return []
  return [
    { label: 'Users', value: o.users_total, icon: 'group' },
    { label: 'Parcels', value: o.parcels_total, icon: 'map' },
    { label: 'Vacant', value: o.parcels_vacant, icon: 'grass' },
    { label: 'Verdicts', value: o.verdicts_total, icon: 'gavel' },
    { label: 'Deeds', value: o.deeds_total, icon: 'description' },
    { label: 'Saved searches', value: o.saved_searches_total, icon: 'saved_search' },
    { label: 'Neighborhoods', value: o.neighborhoods_total, icon: 'location_city' },
  ]
})

function statusColor(status: string): string {
  if (status === 'success') return 'positive'
  if (status === 'failed') return 'negative'
  if (status === 'running') return 'primary'
  if (status === 'queued') return 'orange'
  return 'grey-6'
}

function formatTime(value: string | null): string {
  if (value === null) return '—'
  return new Date(value).toLocaleString()
}

async function load(): Promise<void> {
  if (!isAdmin.value) return
  loading.value = true
  try {
    overview.value = await api.getAdminOverview()
    datasets.value = await api.getAdminDatasets()
    const page = await api.getAdminUsers(100, 0)
    users.value = page.users
    usersTotal.value = page.total
    await loadJobs()
  } finally {
    loading.value = false
  }
}

async function patchUser(
  target: User,
  payload: { role?: string; tier?: string; is_active?: boolean },
): Promise<void> {
  try {
    const updated = await api.updateAdminUser(target.id, payload)
    const index = users.value.findIndex((u) => u.id === updated.id)
    if (index !== -1) users.value[index] = updated
    $q.notify({ type: 'positive', message: `Updated ${updated.email}.` })
  } catch {
    $q.notify({ type: 'negative', message: 'Could not update the user.' })
    void load()
  }
}

onMounted(() => void load())

onBeforeUnmount(() => {
  if (pollTimer !== null) clearInterval(pollTimer)
})
</script>

<template>
  <q-page class="q-pa-md">
    <div v-if="!isAdmin" class="empty">
      <q-icon name="lock" size="48px" color="grey-5" />
      <div class="text-subtitle1 text-grey-7 q-mt-sm">Administrator access required</div>
    </div>

    <div v-else class="admin-wrap">
      <q-inner-loading :showing="loading" color="primary" />

      <div class="cards">
        <q-card v-for="card in overviewCards" :key="card.label" flat bordered class="stat-card">
          <q-icon :name="card.icon" size="22px" class="text-primary" />
          <div class="stat-value">{{ card.value.toLocaleString() }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </q-card>
      </div>

      <div class="text-subtitle2 q-mt-md q-mb-xs">
        Jobs
        <q-spinner v-if="hasActiveRun" color="primary" size="14px" class="q-ml-xs" />
      </div>
      <div class="job-groups">
        <q-card v-for="group in jobGroups" :key="group.title" flat bordered class="job-group">
          <div class="job-group-title">{{ group.title }}</div>
          <div v-for="job in group.items" :key="job.id" class="job-row">
            <div class="job-meta">
              <div class="job-label">{{ job.label }}</div>
              <div class="job-sub">
                <q-badge
                  v-if="job.latest_run"
                  :color="statusColor(job.latest_run.status)"
                  text-color="white"
                >
                  {{ job.latest_run.status }}
                </q-badge>
                <span class="job-time">{{
                  job.latest_run ? formatTime(job.latest_run.finished_at ?? job.latest_run.created_at) : 'never run'
                }}</span>
              </div>
            </div>
            <q-btn
              dense
              unelevated
              color="primary"
              :label="job.params.length > 0 ? 'Run…' : 'Run'"
              :loading="submittingJob === job.id"
              :disable="jobIsBusy(job)"
              @click="() => startRun(job)"
            />
          </div>
        </q-card>
      </div>

      <div class="text-subtitle2 q-mt-md q-mb-xs">Recent runs</div>
      <q-markup-table flat bordered dense>
        <thead>
          <tr>
            <th class="text-left">Job</th>
            <th class="text-left">Status</th>
            <th class="text-right">Rows</th>
            <th class="text-left">Started</th>
            <th class="text-left">Finished</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in jobRuns" :key="run.id">
            <td class="text-left">{{ run.label }}</td>
            <td class="text-left">
              <q-badge :color="statusColor(run.status)" text-color="white">{{ run.status }}</q-badge>
              <q-tooltip v-if="run.error">{{ run.error }}</q-tooltip>
            </td>
            <td class="text-right">{{ run.result_count?.toLocaleString() ?? '—' }}</td>
            <td class="text-left">{{ formatTime(run.started_at) }}</td>
            <td class="text-left">{{ formatTime(run.finished_at) }}</td>
          </tr>
          <tr v-if="jobRuns.length === 0">
            <td colspan="5" class="text-grey-6">No jobs have been triggered yet.</td>
          </tr>
        </tbody>
      </q-markup-table>

      <div class="text-subtitle2 q-mt-md q-mb-xs">Pull data from the server</div>
      <q-card flat bordered class="pull-card">
        <div class="text-caption text-grey-7 q-mb-sm">
          The server fetches the URL and streams the file to your browser — use it for sources this
          server can reach but your machine can't.
        </div>
        <div class="pull-row">
          <q-input
            v-model="fetchUrl"
            label="URL to fetch"
            dense
            outlined
            class="pull-input"
            @keyup.enter="() => pullSource(fetchUrl)"
          />
          <q-btn
            unelevated
            color="primary"
            label="Pull"
            :loading="pulling"
            :disable="fetchUrl.trim() === ''"
            @click="() => pullSource(fetchUrl)"
          />
        </div>
        <div v-if="fetchSources.length > 0" class="pull-shortcuts">
          <q-chip
            v-for="source in fetchSources"
            :key="source.url"
            clickable
            dense
            color="grey-3"
            text-color="grey-9"
            @click="() => (fetchUrl = source.url)"
          >
            {{ source.label }}
            <q-tooltip>{{ source.description }}</q-tooltip>
          </q-chip>
        </div>
      </q-card>

      <div class="text-subtitle2 q-mt-md q-mb-xs">Dataset freshness</div>
      <q-markup-table flat bordered dense>
        <thead>
          <tr>
            <th class="text-left">Dataset</th>
            <th class="text-left">Status</th>
            <th class="text-right">Rows</th>
            <th class="text-left">Last success</th>
            <th class="text-left">Last attempt</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in datasets" :key="d.dataset">
            <td class="text-left">{{ d.dataset }}</td>
            <td class="text-left">
              <q-badge :color="statusColor(d.status)" text-color="white">{{ d.status }}</q-badge>
            </td>
            <td class="text-right">{{ d.row_count?.toLocaleString() ?? '—' }}</td>
            <td class="text-left">{{ formatTime(d.last_success_at) }}</td>
            <td class="text-left">{{ formatTime(d.last_attempt_at) }}</td>
          </tr>
          <tr v-if="datasets.length === 0">
            <td colspan="5" class="text-grey-6">No ingestion has run yet.</td>
          </tr>
        </tbody>
      </q-markup-table>

      <div class="text-subtitle2 q-mt-md q-mb-xs">Users ({{ usersTotal }})</div>
      <q-markup-table flat bordered dense>
        <thead>
          <tr>
            <th class="text-left">Email</th>
            <th class="text-left">Tier</th>
            <th class="text-left">Role</th>
            <th class="text-left">Active</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td class="text-left">{{ u.email }}</td>
            <td class="text-left" style="width: 130px">
              <q-select
                :model-value="u.tier"
                :options="TIERS"
                dense
                outlined
                options-dense
                @update:model-value="(value: string) => patchUser(u, { tier: value })"
              />
            </td>
            <td class="text-left" style="width: 120px">
              <q-select
                :model-value="u.role"
                :options="ROLES"
                dense
                outlined
                options-dense
                @update:model-value="(value: string) => patchUser(u, { role: value })"
              />
            </td>
            <td class="text-left">
              <q-toggle
                :model-value="u.is_active"
                color="positive"
                @update:model-value="(value: boolean) => patchUser(u, { is_active: value })"
              />
            </td>
          </tr>
        </tbody>
      </q-markup-table>

      <q-dialog v-model="paramDialog">
        <q-card class="param-card">
          <div class="text-subtitle1 q-mb-sm">{{ paramJob?.label }}</div>
          <div v-if="paramJob" class="param-fields">
            <q-input
              v-for="param in paramJob.params"
              :key="param.name"
              v-model="paramValues[param.name]"
              :label="param.label"
              :type="param.type === 'date' ? 'date' : 'text'"
              dense
              outlined
              stack-label
            />
          </div>
          <div class="param-actions">
            <q-btn flat label="Cancel" @click="paramDialog = false" />
            <q-btn unelevated color="primary" label="Run" @click="submitParams" />
          </div>
        </q-card>
      </q-dialog>
    </div>
  </q-page>
</template>

<style scoped>
.admin-wrap {
  max-width: 960px;
  margin: 0 auto;
  position: relative;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
}
.stat-card {
  padding: 12px;
  border-radius: var(--lot-radius);
  text-align: center;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--lot-ink);
  margin-top: 4px;
}
.stat-label {
  font-size: 12px;
  color: var(--lot-muted);
}
.empty {
  text-align: center;
  padding: 64px 16px;
}
.job-groups {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}
.job-group {
  padding: 10px 12px;
  border-radius: var(--lot-radius);
}
.job-group-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 6px;
}
.job-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 0;
  border-top: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.06));
}
.job-row:first-of-type {
  border-top: none;
}
.job-label {
  font-size: 13px;
  color: var(--lot-ink);
}
.job-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}
.job-time {
  font-size: 11px;
  color: var(--lot-muted);
}
.param-card {
  padding: 16px;
  min-width: 340px;
}
.param-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.param-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.pull-card {
  padding: 12px;
  border-radius: var(--lot-radius);
}
.pull-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pull-input {
  flex: 1;
}
.pull-shortcuts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
</style>
