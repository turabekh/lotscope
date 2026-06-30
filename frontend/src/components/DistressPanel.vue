<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import type { DistressTier } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const { distress } = storeToRefs(useParcelStore())

interface TierStyle {
  label: string
  color: string
  icon: string
}

const TIER: Record<DistressTier, TierStyle> = {
  high: { label: 'High seller motivation', color: 'negative', icon: 'local_fire_department' },
  medium: { label: 'Some seller motivation', color: 'warning', icon: 'trending_up' },
  low: { label: 'Mild distress signals', color: 'blue-grey-6', icon: 'info' },
  none: { label: 'No distress signals', color: 'positive', icon: 'check_circle' },
}

const tierStyle = computed(() => (distress.value ? TIER[distress.value.tier] : TIER.none))
</script>

<template>
  <q-card v-if="distress" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="sell" size="18px" class="q-mr-xs" />Motivated seller
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          A distress index from tax delinquency, sheriff sale, liens, L&I, vacancy, and absentee
          ownership. Higher means the owner is more likely a motivated seller. Informational.
        </q-tooltip>
        <q-space />
        <q-chip dense square :color="tierStyle.color" text-color="white" :icon="tierStyle.icon">
          {{ distress.score }}/100
        </q-chip>
      </div>

      <div class="text-body2 text-weight-medium" :class="`text-${tierStyle.color}`">
        {{ tierStyle.label }}
      </div>

      <div v-if="distress.factors.length" class="factor-list q-mt-sm">
        <div v-for="factor in distress.factors" :key="factor.code" class="factor">
          <span class="factor-label">{{ factor.label }}</span>
          <span class="factor-weight">+{{ factor.weight }}</span>
        </div>
      </div>
      <div v-else class="text-body2 text-grey-6 q-mt-xs">
        No tax, L&I, vacancy, or absentee-owner distress signals on record.
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.rounded-borders {
  border-radius: var(--lot-radius) !important;
  box-shadow: var(--lot-shadow);
}
.section-title {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 6px;
}
.factor-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.factor {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-negative-soft);
}
.factor-label {
  font-size: 12.5px;
  color: var(--lot-ink);
}
.factor-weight {
  font-size: 11px;
  font-weight: 700;
  color: var(--lot-sev-high);
  flex-shrink: 0;
  margin-left: 8px;
}
</style>
