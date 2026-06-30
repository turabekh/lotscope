<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import UserMenu from '@/components/UserMenu.vue'
import { useCompareStore } from '@/stores/compare'
import { useThemeStore } from '@/stores/theme'
import { useWatchlistStore } from '@/stores/watchlist'

defineProps<{ title?: string }>()

const route = useRoute()
const theme = useThemeStore()
const watchlist = useWatchlistStore()
const compare = useCompareStore()
const { alerts } = storeToRefs(watchlist)
const { count: compareCount } = storeToRefs(compare)

interface NavLink {
  label: string
  icon: string
  name: string
  badge?: () => number
}

const links = computed<NavLink[]>(() => [
  { label: 'Explore', icon: 'travel_explore', name: 'map' },
  { label: 'Watchlist', icon: 'bookmark', name: 'watchlist', badge: () => alerts.value },
  { label: 'Pipeline', icon: 'view_kanban', name: 'pipeline' },
  { label: 'Compare', icon: 'compare_arrows', name: 'compare', badge: () => compareCount.value },
])

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <q-header class="app-header">
    <q-toolbar class="app-toolbar">
      <slot name="lead" />

      <router-link :to="{ name: 'map' }" class="brand" aria-label="LotScope home">
        <span class="brand-mark">◧</span>
        <span class="brand-name">LotScope <span class="brand-sub">PHL</span></span>
      </router-link>

      <template v-if="title">
        <q-separator vertical inset class="brand-div gt-xs" />
        <span class="page-title gt-xs">{{ title }}</span>
      </template>

      <q-space />

      <nav class="nav gt-sm">
        <q-btn
          v-for="link in links"
          :key="link.name"
          flat
          no-caps
          dense
          :icon="link.icon"
          :label="link.label"
          class="nav-link"
          :class="{ active: isActive(link.name) }"
          :to="{ name: link.name }"
        >
          <q-badge
            v-if="link.badge && link.badge() > 0"
            color="negative"
            rounded
            floating
            class="nav-badge"
          >
            {{ link.badge() }}
          </q-badge>
        </q-btn>
      </nav>

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
        <q-tooltip anchor="bottom middle" self="top middle">{{ theme.label }} — click to change</q-tooltip>
      </q-btn>

      <UserMenu />
    </q-toolbar>
  </q-header>
</template>

<style scoped>
.app-header {
  background: var(--lot-surface);
  color: var(--lot-ink);
  border-bottom: 1px solid var(--lot-border);
  box-shadow: var(--lot-shadow-sm);
}
.app-toolbar {
  min-height: 54px;
  padding-left: 10px;
  padding-right: 10px;
  gap: 2px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--lot-ink);
  padding: 4px 6px;
  border-radius: var(--lot-radius-sm);
}
.brand:hover {
  background: var(--lot-surface-2);
}
.brand-mark {
  color: var(--lot-accent);
  font-size: 20px;
  line-height: 1;
}
.brand-name {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.01em;
}
.brand-sub {
  font-weight: 500;
  color: var(--lot-faint);
}
.brand-div {
  height: 22px;
  margin: 0 6px;
}
.page-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--lot-muted);
}
.nav {
  display: flex;
  align-items: center;
  gap: 2px;
}
.nav-link {
  color: var(--lot-muted);
  padding: 4px 12px;
  border-radius: var(--lot-radius-sm);
  font-weight: 500;
}
.nav-link.active {
  color: var(--lot-accent-ink);
  background: var(--lot-accent-soft);
}
.nav-badge {
  font-size: 9px;
}
</style>
