<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'
import { useThemeStore } from '@/stores/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const market = useMarketStore()
const route = useRoute()

theme.init()

const showShell = computed(() => route.meta.requiresAuth === true)

const authResolved = ref(false)

const FALLBACK_CHECK_MS = 5 * 60 * 1000
let refreshTimer: ReturnType<typeof setTimeout> | undefined

function scheduleRefresh(): void {
  if (refreshTimer !== undefined) clearTimeout(refreshTimer)
  const due = auth.millisecondsUntilNextRefresh()
  const delay = due === null ? FALLBACK_CHECK_MS : Math.min(Math.max(due, 1000), FALLBACK_CHECK_MS)
  refreshTimer = setTimeout(() => {
    void rollSession()
  }, delay)
}

async function rollSession(): Promise<void> {
  if (document.visibilityState === 'visible') await auth.refreshIfExpiring()
  scheduleRefresh()
}

function onVisibilityChange(): void {
  void rollSession()
}

onMounted(async () => {
  await auth.ensureRestored()
  authResolved.value = true
  void market.load()
  scheduleRefresh()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  if (refreshTimer !== undefined) clearTimeout(refreshTimer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <AppShell v-if="showShell">
    <router-view v-if="authResolved" />
    <div v-else class="auth-boot">
      <q-spinner size="32px" color="primary" />
    </div>
  </AppShell>
  <router-view v-else />
</template>

<style scoped>
.auth-boot {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
</style>
