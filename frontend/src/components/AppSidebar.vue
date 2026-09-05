<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useWatchlistStore } from '@/stores/watchlist'

withDefaults(defineProps<{ collapsed: boolean; mobile?: boolean }>(), { mobile: false })
const emit = defineEmits<{ toggle: []; navigate: [] }>()

const route = useRoute()
const auth = useAuthStore()
const { user } = storeToRefs(auth)
const { alerts } = storeToRefs(useWatchlistStore())

interface NavLink {
  label: string
  icon: string
  name: string
  badge?: () => number
}

const sections = computed<NavLink[]>(() => [
  { label: 'Analyst', icon: 'forum', name: 'analyst' },
  { label: 'Deals', icon: 'view_kanban', name: 'deals' },
  { label: 'Packets', icon: 'description', name: 'packets', badge: () => alerts.value },
])

function visible(links: NavLink[]): NavLink[] {
  return links.filter(() => true)
}

const visibleSections = computed<NavLink[]>(() => visible(sections.value))

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <div class="sidebar column no-wrap fit">
    <router-link :to="{ name: 'analyst' }" class="brand" aria-label="LotScope analyst">
      <span class="brand-mark">◧</span>
      <span v-if="!collapsed" class="brand-name">LotScope <span class="brand-sub">PHL</span></span>
    </router-link>

    <div v-if="!mobile" class="switcher-slot" :class="{ mini: collapsed }"></div>

    <q-list class="nav" data-test="nav-primary">
      <q-item
        v-for="item in visibleSections"
        :key="item.name"
        v-ripple
        clickable
        :active="isActive(item.name)"
        active-class="nav-active"
        class="nav-item"
        :to="{ name: item.name }"
        @click="emit('navigate')"
      >
        <q-item-section avatar class="nav-avatar">
          <q-icon :name="item.icon" size="21px" />
          <q-badge
            v-if="item.badge && item.badge() > 0"
            color="negative"
            rounded
            floating
            class="nav-badge"
          >
            {{ item.badge() }}
          </q-badge>
        </q-item-section>
        <q-item-section v-if="!collapsed">{{ item.label }}</q-item-section>
        <q-tooltip v-if="collapsed" anchor="center right" self="center left">
          {{ item.label }}
        </q-tooltip>
      </q-item>
    </q-list>

    <q-space />

    <q-list class="nav footer">
      <q-item
        v-ripple
        clickable
        :active="isActive('account')"
        active-class="nav-active"
        class="nav-item"
        :to="{ name: 'account' }"
        @click="emit('navigate')"
      >
        <q-item-section avatar class="nav-avatar"
          ><q-icon name="manage_accounts" size="21px"
        /></q-item-section>
        <q-item-section v-if="!collapsed">Account</q-item-section>
        <q-tooltip v-if="collapsed" anchor="center right" self="center left">Account</q-tooltip>
      </q-item>
      <q-item
        v-if="user?.role === 'admin'"
        v-ripple
        clickable
        :active="isActive('admin')"
        active-class="nav-active"
        class="nav-item"
        :to="{ name: 'admin' }"
        @click="emit('navigate')"
      >
        <q-item-section avatar class="nav-avatar"
          ><q-icon name="admin_panel_settings" size="21px"
        /></q-item-section>
        <q-item-section v-if="!collapsed">Admin</q-item-section>
        <q-tooltip v-if="collapsed" anchor="center right" self="center left">Admin</q-tooltip>
      </q-item>
      <q-item v-if="!mobile" v-ripple clickable class="nav-item" @click="emit('toggle')">
        <q-item-section avatar class="nav-avatar">
          <q-icon :name="collapsed ? 'chevron_right' : 'chevron_left'" size="21px" />
        </q-item-section>
        <q-item-section v-if="!collapsed">Collapse</q-item-section>
        <q-tooltip v-if="collapsed" anchor="center right" self="center left">Expand</q-tooltip>
      </q-item>
    </q-list>
  </div>
</template>

<style scoped>
.sidebar {
  background: var(--lot-surface);
  padding: 12px 8px;
  gap: 2px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--lot-ink);
  padding: 6px 8px;
  border-radius: var(--lot-radius-sm);
  margin-bottom: 8px;
}
.brand:hover {
  background: var(--lot-surface-2);
}
.brand-mark {
  color: var(--lot-accent);
  font-size: 22px;
  line-height: 1;
}
.brand-name {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.01em;
  white-space: nowrap;
}
.brand-sub {
  font-weight: 500;
  color: var(--lot-faint);
}
.switcher-slot {
  margin-bottom: 10px;
}
.nav {
  padding: 0;
}
.nav-item {
  border-radius: var(--lot-radius-sm);
  min-height: 42px;
  color: var(--lot-muted);
  font-weight: 500;
}
.nav-avatar {
  min-width: 32px;
  padding-right: 0;
}
.nav-active {
  color: var(--lot-accent-ink);
  background: var(--lot-accent-soft);
}
.nav-badge {
  font-size: 9px;
}
.footer {
  color: var(--lot-muted);
}
.research {
  color: var(--lot-muted);
  border-radius: var(--lot-radius-sm);
}
.nav-nested {
  padding-left: 10px;
  min-height: 38px;
}
</style>
