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

const usageRatio = computed(() => {
  if (!usage.value || usage.value.limit === null || usage.value.limit === 0) return 0
  return Math.min(1, usage.value.used / usage.value.limit)
})

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

          <q-card-section>
            <div class="text-overline text-grey-7">AI questions today</div>
            <template v-if="usage">
              <div class="row items-baseline">
                <div class="text-h5 text-weight-bold">{{ usage.used }}</div>
                <div class="text-subtitle1 text-grey-7 q-ml-xs">
                  / {{ usage.limit === null ? 'unlimited' : usage.limit }}
                </div>
                <q-space />
                <div v-if="usage.remaining !== null" class="text-body2 text-grey-7">
                  {{ usage.remaining }} left today
                </div>
              </div>
              <q-linear-progress
                v-if="usage.limit !== null"
                :value="usageRatio"
                size="10px"
                rounded
                class="q-mt-sm"
                :color="usageRatio >= 1 ? 'negative' : usageRatio >= 0.8 ? 'warning' : 'primary'"
                track-color="grey-3"
              />
              <div class="text-caption text-grey-6 q-mt-xs">Resets daily.</div>
            </template>
            <div v-else class="text-body2 text-grey-6">Loading usage…</div>
          </q-card-section>

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
