<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const route = useRoute()

theme.init()

const showShell = computed(() => route.meta.requiresAuth === true)

const REFRESH_INTERVAL_MS = 30 * 60 * 1000
let refreshTimer: ReturnType<typeof setInterval> | undefined

function rollSession(): void {
  if (document.visibilityState === 'visible') void auth.refresh()
}

onMounted(async () => {
  await auth.restore()
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
    <router-view />
  </AppShell>
  <router-view v-else />
</template>
