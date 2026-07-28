<script setup lang="ts">
import { computed } from 'vue'

import { launchStatusDisplay } from '@/lib/market-status'
import { MARKET_LABELS, useMarketStore } from '@/stores/market'

const market = useMarketStore()

const label = computed(() => MARKET_LABELS[market.active])
const status = computed(() => launchStatusDisplay(market.activeInfo?.launch_status))
const known = computed(() => market.activeInfo !== null)
const isPilot = computed(() => status.value.presentation === 'pilot')
const suffix = computed(() => status.value.badge ?? 'coverage')
</script>

<template>
  <div v-if="known" class="coverage" role="note">
    <q-icon name="dataset" size="15px" class="coverage-icon" />
    <span class="coverage-label">{{ label }} · {{ suffix }}</span>
    <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
      <template v-if="isPilot">
        {{ label }} pilot — county assessment &amp; geometry, provided as-is. No open sale-price
        comps or code-enforcement feed; zoning provisional.
      </template>
      <template v-else>
        {{ status.summary }} Zoning, sales, and L&amp;I from {{ label }} open data, provided as-is.
      </template>
    </q-tooltip>
  </div>
</template>

<style scoped>
.coverage {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: 1px solid var(--lot-border);
  border-radius: var(--lot-radius-pill);
  background: var(--lot-surface-2);
  color: var(--lot-muted);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  cursor: default;
}
.coverage-icon {
  color: var(--lot-faint);
}
</style>
