<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()
const { user, isAuthenticated } = storeToRefs(store)
const router = useRouter()

const initial = computed(() => (user.value?.email ?? '?').charAt(0).toUpperCase())

function signOut(): void {
  store.logout()
  void router.push('/')
}

function goAccount(): void {
  void router.push({ name: 'account' })
}

function goLeads(): void {
  void router.push({ name: 'leads' })
}

function goWatchlist(): void {
  void router.push({ name: 'watchlist' })
}
</script>

<template>
  <q-btn
    v-if="!isAuthenticated"
    flat
    dense
    no-caps
    icon="login"
    label="Sign in"
    :to="{ name: 'login' }"
  />
  <q-btn v-else flat dense round aria-label="Account">
    <q-avatar size="30px" color="white" text-color="primary" class="text-weight-bold">
      {{ initial }}
    </q-avatar>
    <q-menu anchor="bottom right" self="top right">
      <q-list style="min-width: 200px">
        <q-item>
          <q-item-section>
            <q-item-label class="ellipsis">{{ user?.full_name ?? user?.email }}</q-item-label>
            <q-item-label caption>{{ user?.email }} · {{ user?.tier }} plan</q-item-label>
          </q-item-section>
        </q-item>
        <q-separator />
        <q-item v-close-popup clickable @click="goWatchlist">
          <q-item-section avatar><q-icon name="bookmark" /></q-item-section>
          <q-item-section>My watchlist</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goLeads">
          <q-item-section avatar><q-icon name="sell" /></q-item-section>
          <q-item-section>Motivated-seller leads</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goAccount">
          <q-item-section avatar><q-icon name="manage_accounts" /></q-item-section>
          <q-item-section>Account & usage</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="signOut">
          <q-item-section avatar><q-icon name="logout" /></q-item-section>
          <q-item-section>Sign out</q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>
