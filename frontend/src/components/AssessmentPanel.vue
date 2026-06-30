<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency } from '@/lib/format'
import type { AssessmentStatus } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const { assessment } = storeToRefs(useParcelStore())

interface StatusStyle {
  label: string
  color: string
  icon: string
}

const STATUS: Record<AssessmentStatus, StatusStyle> = {
  over_assessed: { label: 'Over-assessed', color: 'warning', icon: 'trending_down' },
  fairly_assessed: { label: 'Fairly assessed', color: 'blue-grey-6', icon: 'balance' },
  under_assessed: { label: 'Under-assessed', color: 'positive', icon: 'trending_up' },
  unknown: { label: 'Not enough data', color: 'grey-6', icon: 'help' },
}

const style = computed(() => (assessment.value ? STATUS[assessment.value.status] : STATUS.unknown))
const reason = computed(() => assessment.value?.reasons[0] ?? '')
</script>

<template>
  <q-card
    v-if="assessment && assessment.status !== 'unknown'"
    flat
    bordered
    class="rounded-borders"
  >
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="account_balance" size="18px" class="q-mr-xs" />Assessment vs. market
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          Compares the city's assessed market value against LotScope's comp-based estimate. An
          over-assessment may support a tax appeal. Informational, not tax advice.
        </q-tooltip>
        <q-space />
        <q-chip dense square :color="style.color" text-color="white" :icon="style.icon">
          {{ style.label }}
        </q-chip>
      </div>

      <div class="figures q-mt-xs">
        <div class="figure">
          <span class="figure-label">Assessed</span>
          <span class="figure-value">{{ formatCurrency(assessment.assessed_market_value) }}</span>
        </div>
        <div class="figure">
          <span class="figure-label">Market est.</span>
          <span class="figure-value">{{ formatCurrency(assessment.market_estimate) }}</span>
        </div>
      </div>

      <div
        v-if="assessment.estimated_annual_tax_savings"
        class="savings q-mt-sm"
      >
        <q-icon name="savings" size="16px" class="q-mr-xs" />
        Est. appeal savings ~{{ formatCurrency(assessment.estimated_annual_tax_savings) }}/yr
      </div>

      <div v-if="reason" class="text-body2 text-grey-7 q-mt-sm">{{ reason }}</div>

      <div class="text-caption text-grey-5 q-mt-sm">
        {{ assessment.confidence }} confidence · {{ assessment.disclaimer }}
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
  color: #5b6b7d;
  margin-bottom: 6px;
}
.figures {
  display: flex;
  gap: 10px;
}
.figure {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 6px 10px;
  border-radius: var(--lot-radius-sm);
  background: #f4f6f8;
}
.figure-label {
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #7b8794;
}
.figure-value {
  font-size: 14px;
  font-weight: 700;
  color: #1f2933;
}
.savings {
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  color: #1b7a4b;
  padding: 6px 10px;
  border-radius: var(--lot-radius-sm);
  background: #eef8f2;
}
</style>
