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

const REFRESH_INTERVAL_MS = 30 * 60 * 1000
let refreshTimer: ReturnType<typeof setInterval> | undefined

function rollSession(): void {
  if (document.visibilityState === 'visible') void auth.refresh()
}

onMounted(async () => {
  await auth.ensureRestored()
  authResolved.value = true
  void market.load()
  refreshTimer = setInterval(rollSession, REFRESH_INTERVAL_MS)
  document.addEventListener('visibilitychange', rollSession)
})

onUnmounted(() => {
  if (refreshTimer !== undefined) clearInterval(refreshTimer)
  document.removeEventListener('visibilitychange', rollSession)
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
