<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/lib/api'
import type { AdminOverview, DatasetStatus, User } from '@/lib/types'
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
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat dense round icon="arrow_back" to="/app" aria-label="Back to map" />
        <q-toolbar-title>Admin console</q-toolbar-title>
      </q-toolbar>
    </q-header>

    <q-page-container>
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
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
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
</style>
