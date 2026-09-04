<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const emit = defineEmits<{ more: [] }>()

const route = useRoute()
const { alerts } = storeToRefs(useWatchlistStore())
const { newTotal } = storeToRefs(useSavedSearchesStore())

const MORE_ROUTES = new Set(['pipeline', 'lists', 'account', 'admin'])
const moreBadge = computed(() => alerts.value + newTotal.value)

interface Tab {
  label: string
  icon: string
  name: string
}

const tabs: Tab[] = [
  { label: 'Home', icon: 'home', name: 'home' },
  { label: 'Find lots', icon: 'travel_explore', name: 'explore' },
  { label: 'Leads', icon: 'sell', name: 'leads' },
]

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <nav class="tabbar" aria-label="Primary">
    <router-link
      v-for="tab in tabs"
      :key="tab.name"
      class="tab"
      :class="{ active: isActive(tab.name) }"
      :to="{ name: tab.name }"
    >
      <q-icon :name="tab.icon" size="22px" />
      <span>{{ tab.label }}</span>
    </router-link>
    <button
      type="button"
      class="tab"
      :class="{ active: MORE_ROUTES.has(String(route.name)) }"
      @click="emit('more')"
    >
      <q-icon name="more_horiz" size="22px" />
      <q-badge v-if="moreBadge > 0" color="negative" rounded floating>{{ moreBadge }}</q-badge>
      <span>More</span>
    </button>
  </nav>
</template>

<style scoped>
.tabbar {
  display: flex;
  background: var(--lot-surface);
  border-top: 1px solid var(--lot-border);
  padding-bottom: env(safe-area-inset-bottom);
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 52px;
  padding: 6px 2px;
  position: relative;
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: none;
  color: var(--lot-muted);
  font-size: 11px;
  font-weight: 500;
}
.tab.active {
  color: var(--lot-accent-ink);
}
</style>
