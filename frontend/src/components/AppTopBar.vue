<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import GlobalSearch from '@/components/GlobalSearch.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const theme = useThemeStore()
const $q = useQuasar()

const isMobile = computed(() => $q.screen.lt.md)
const isNarrow = computed(() => $q.screen.lt.sm)
const title = computed(() => {
  if (isMobile.value) return ''
  if (route.name === 'sheriff-sales' && 'Sheriff sales') {
    return 'Sheriff sales'
  }
  return route.meta.title ?? ''
})
</script>

<template>
  <q-header class="topbar">
    <q-toolbar class="topbar-toolbar">
      <span v-if="title" class="page-title">{{ title }}</span>
      <GlobalSearch v-if="!isNarrow" />
      <slot name="lead" />

      <q-space />

      <slot name="actions" />

      <GlobalSearch v-if="isNarrow" />

      <q-btn
        v-if="!isMobile"
        flat
        dense
        round
        :icon="theme.icon"
        class="q-ml-sm"
        :aria-label="theme.label"
        @click="theme.cycle()"
      >
        <q-tooltip anchor="bottom middle" self="top middle"
          >{{ theme.label }} — click to change</q-tooltip
        >
      </q-btn>

      <UserMenu />
    </q-toolbar>
  </q-header>
</template>

<style scoped>
.topbar {
  background: var(--lot-surface);
  color: var(--lot-ink);
  border-bottom: 1px solid var(--lot-border);
  box-shadow: var(--lot-shadow-sm);
}
.topbar-toolbar {
  min-height: 54px;
  padding-left: 12px;
  padding-right: 8px;
  gap: 6px;
}
.topbar-toolbar :deep(.global-search) {
  min-width: 0;
}
.page-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--lot-ink);
}
</style>
