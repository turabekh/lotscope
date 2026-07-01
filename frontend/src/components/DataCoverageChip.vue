<script setup lang="ts">
import { computed } from 'vue'

import { MARKET_LABELS, useMarketStore } from '@/stores/market'

const market = useMarketStore()

const label = computed(() => MARKET_LABELS[market.active])
</script>

<template>
  <div class="coverage" role="note">
    <q-icon name="dataset" size="15px" class="coverage-icon" />
    <span class="coverage-label">{{ label }} · city data</span>
    <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
      Zoning, sales, and L&amp;I from {{ label }} open data, provided as-is.
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
