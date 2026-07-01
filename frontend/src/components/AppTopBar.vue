<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import UserMenu from '@/components/UserMenu.vue'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const theme = useThemeStore()

const title = computed(() => route.meta.title ?? '')
</script>

<template>
  <q-header class="topbar">
    <q-toolbar class="topbar-toolbar">
      <span v-if="title" class="page-title">{{ title }}</span>
      <slot name="lead" />

      <q-space />

      <slot name="actions" />

      <q-btn
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
  padding-left: 16px;
  padding-right: 10px;
  gap: 4px;
}
.page-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--lot-ink);
}
</style>
