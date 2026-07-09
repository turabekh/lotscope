<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import DataCoverageChip from '@/components/DataCoverageChip.vue'
import GlobalSearch from '@/components/GlobalSearch.vue'
import MarketSwitcher from '@/components/MarketSwitcher.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useMarketStore } from '@/stores/market'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const market = useMarketStore()
const theme = useThemeStore()
const $q = useQuasar()

const isMobile = computed(() => $q.screen.lt.md)
const title = computed(() => {
  if (isMobile.value) return ''
  if (route.name === 'sheriff-sales' && market.activeInfo?.forced_sale_surface_label) {
    return market.activeInfo.forced_sale_surface_label
  }
  return route.meta.title ?? ''
})
</script>

<template>
  <q-header class="topbar">
    <q-toolbar class="topbar-toolbar">
      <MarketSwitcher v-if="isMobile" variant="pill" class="q-mr-xs" />
      <span v-if="title" class="page-title">{{ title }}</span>
      <GlobalSearch />
      <slot name="lead" />

      <q-space />

      <slot name="actions" />

      <DataCoverageChip v-if="!isMobile" class="q-mr-xs" />

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
