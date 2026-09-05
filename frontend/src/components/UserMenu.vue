<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useWatchlistStore } from '@/stores/watchlist'

const store = useAuthStore()
const { user, isAuthenticated } = storeToRefs(store)
const watchlist = useWatchlistStore()
const { alerts } = storeToRefs(watchlist)
const router = useRouter()
const theme = useThemeStore()

const initial = computed(() => (user.value?.email ?? '?').charAt(0).toUpperCase())

watch(
  isAuthenticated,
  (value) => {
    if (value) {
      void watchlist.ensureLoaded()
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

function goDeals(): void {
  void router.push({ name: 'deals' })
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
    <q-avatar size="30px" color="primary" text-color="white" class="text-weight-bold">
      {{ initial }}
    </q-avatar>
    <q-badge v-if="alerts > 0" color="negative" floating rounded>{{ alerts }}</q-badge>
    <q-menu anchor="bottom right" self="top right">
      <q-list style="min-width: 200px">
        <q-item>
          <q-item-section>
            <q-item-label class="ellipsis">{{ user?.full_name ?? user?.email }}</q-item-label>
            <q-item-label caption>{{ user?.email }} · {{ user?.tier }} plan</q-item-label>
          </q-item-section>
        </q-item>
        <q-separator />
        <q-item v-close-popup clickable @click="goDeals">
          <q-item-section avatar><q-icon name="view_kanban" /></q-item-section>
          <q-item-section>Deals</q-item-section>
        </q-item>
        <q-item v-close-popup clickable @click="goAccount">
          <q-item-section avatar><q-icon name="manage_accounts" /></q-item-section>
          <q-item-section>Account & usage</q-item-section>
        </q-item>
        <q-item v-if="user?.role === 'admin'" v-close-popup clickable @click="goAdmin">
          <q-item-section avatar><q-icon name="admin_panel_settings" /></q-item-section>
          <q-item-section>Admin console</q-item-section>
        </q-item>
        <q-item clickable data-test="user-menu-theme" @click="theme.cycle()">
          <q-item-section avatar><q-icon :name="theme.icon" /></q-item-section>
          <q-item-section>{{ theme.label }}</q-item-section>
        </q-item>
        <q-separator />
        <q-item v-close-popup clickable @click="signOut">
          <q-item-section avatar><q-icon name="logout" /></q-item-section>
          <q-item-section>Sign out</q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>
