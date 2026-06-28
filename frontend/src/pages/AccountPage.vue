<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()
const { user, usage } = storeToRefs(store)
const router = useRouter()

onMounted(() => {
  void store.fetchUsage()
})

const metrics = computed(() => {
  if (!usage.value) return []
  return [
    { key: 'views', label: 'Parcels viewed today', icon: 'map', ...usage.value.parcel_views },
    { key: 'ask', label: 'AI questions today', icon: 'forum', ...usage.value.ask },
  ]
})

function ratio(used: number, limit: number | null): number {
  if (limit === null || limit === 0) return 0
  return Math.min(1, used / limit)
}

function barColor(used: number, limit: number | null): string {
  const r = ratio(used, limit)
  return r >= 1 ? 'negative' : r >= 0.8 ? 'warning' : 'primary'
}

async function signOut(): Promise<void> {
  store.logout()
  await router.push('/')
}
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat dense round icon="arrow_back" to="/" aria-label="Back to map" />
        <q-toolbar-title>Account</q-toolbar-title>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="flex flex-center q-pa-md">
        <q-card v-if="user" flat bordered class="account-card">
          <q-card-section class="row items-center q-gutter-md">
            <q-avatar size="56px" color="primary" text-color="white" class="text-h5 text-weight-bold">
              {{ user.email.charAt(0).toUpperCase() }}
            </q-avatar>
            <div>
              <div class="text-h6">{{ user.full_name ?? user.email }}</div>
              <div class="text-grey-7">{{ user.email }}</div>
            </div>
            <q-space />
            <q-chip color="primary" text-color="white" class="text-capitalize">
              {{ user.tier }} plan
            </q-chip>
          </q-card-section>

          <q-separator />

          <q-card-section v-if="usage" class="q-gutter-md">
            <div v-for="m in metrics" :key="m.key">
              <div class="row items-center">
                <q-icon :name="m.icon" size="18px" color="grey-7" class="q-mr-xs" />
                <div class="text-overline text-grey-7">{{ m.label }}</div>
                <q-space />
                <div v-if="m.remaining !== null" class="text-caption text-grey-7">
                  {{ m.remaining }} left
                </div>
              </div>
              <div class="row items-baseline">
                <div class="text-h6 text-weight-bold">{{ m.used }}</div>
                <div class="text-subtitle2 text-grey-7 q-ml-xs">
                  / {{ m.limit === null ? 'unlimited' : m.limit }}
                </div>
              </div>
              <q-linear-progress
                v-if="m.limit !== null"
                :value="ratio(m.used, m.limit)"
                size="9px"
                rounded
                class="q-mt-xs"
                :color="barColor(m.used, m.limit)"
                track-color="grey-3"
              />
            </div>
            <div class="text-caption text-grey-6">Limits reset daily.</div>
          </q-card-section>
          <q-card-section v-else class="text-body2 text-grey-6">Loading usage…</q-card-section>

          <q-separator />

          <q-card-section>
            <div class="row items-center">
              <div>
                <div class="text-subtitle2">Need more questions?</div>
                <div class="text-caption text-grey-7">Paid plans are coming soon.</div>
              </div>
              <q-space />
              <q-btn outline disable color="primary" no-caps label="Upgrade" />
            </div>
          </q-card-section>

          <q-separator />

          <q-card-actions align="right">
            <q-btn flat no-caps color="negative" icon="logout" label="Sign out" @click="signOut" />
          </q-card-actions>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.account-card {
  width: 520px;
  max-width: 94vw;
  border-radius: 14px;
}
</style>
