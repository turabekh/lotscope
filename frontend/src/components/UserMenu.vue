<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useCompareStore } from '@/stores/compare'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const store = useAuthStore()
const { user, isAuthenticated } = storeToRefs(store)
const watchlist = useWatchlistStore()
const { alerts } = storeToRefs(watchlist)
const savedSearches = useSavedSearchesStore()
const { newTotal } = storeToRefs(savedSearches)
const compare = useCompareStore()
const { count: compareCount } = storeToRefs(compare)
const router = useRouter()

const initial = computed(() => (user.value?.email ?? '?').charAt(0).toUpperCase())

watch(
  isAuthenticated,
  (value) => {
    if (value) {
      void watchlist.ensureLoaded()
      void savedSearches.ensureLoaded()
    }
  },
  { immediate: true },
)

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

function goPipeline(): void {
  void router.push({ name: 'pipeline' })
}

function goCompare(): void {
  void router.push({ name: 'compare' })
}

function goSavedSearches(): void {
  void router.push({ name: 'saved-searches' })
}

function goAdmin(): void {
  void router.push({ name: 'admin' })
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
    <q-badge v-if="alerts + newTotal > 0" color="negative" floating rounded>
      {{ alerts + newTotal }}
    </q-badge>
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
          <q-item-section v-if="alerts > 0" side>
            <q-badge color="negative" rounded>{{ alerts }}</q-badge>
          </q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goPipeline">
          <q-item-section avatar><q-icon name="view_kanban" /></q-item-section>
          <q-item-section>Deal pipeline</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goSavedSearches">
          <q-item-section avatar><q-icon name="saved_search" /></q-item-section>
          <q-item-section>Saved searches</q-item-section>
          <q-item-section v-if="newTotal > 0" side>
            <q-badge color="negative" rounded>{{ newTotal }}</q-badge>
          </q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goCompare">
          <q-item-section avatar><q-icon name="compare_arrows" /></q-item-section>
          <q-item-section>Compare parcels</q-item-section>
          <q-item-section v-if="compareCount > 0" side>
            <q-badge color="primary" rounded>{{ compareCount }}</q-badge>
          </q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goLeads">
          <q-item-section avatar><q-icon name="sell" /></q-item-section>
          <q-item-section>Motivated-seller leads</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goAccount">
          <q-item-section avatar><q-icon name="manage_accounts" /></q-item-section>
          <q-item-section>Account & usage</q-item-section>
        </q-item>
        <q-item v-if="user?.role === 'admin'" v-close-popup clickable @click="goAdmin">
          <q-item-section avatar><q-icon name="admin_panel_settings" /></q-item-section>
          <q-item-section>Admin console</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="signOut">
          <q-item-section avatar><q-icon name="logout" /></q-item-section>
          <q-item-section>Sign out</q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>
