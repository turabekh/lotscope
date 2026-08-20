<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import type { ChecklistItem, ChecklistStatus } from '@/lib/types'
import { useParcelStore } from '@/stores/parcel'

const { checklist } = storeToRefs(useParcelStore())

interface StatusStyle {
  icon: string
  color: string
}

const STATUS: Record<ChecklistStatus, StatusStyle> = {
  pass: { icon: 'check_circle', color: 'positive' },
  fail: { icon: 'cancel', color: 'negative' },
  potential_issue: { icon: 'warning', color: 'warning' },
  not_evaluated: { icon: 'radio_button_unchecked', color: 'grey-6' },
  not_applicable: { icon: 'remove', color: 'grey-5' },
}

const AVAILABILITY: Record<string, StatusStyle> = {
  no_data_source: { icon: 'do_not_disturb_on', color: 'grey-5' },
  pending_load: { icon: 'downloading', color: 'blue-grey-4' },
}

function styleFor(item: ChecklistItem): StatusStyle {
  const avail = item.availability ?? 'available'
  return avail !== 'available' ? AVAILABILITY[avail] : STATUS[item.status]
}

const headline = computed(() => {
  const summary = checklist.value?.summary
  if (!summary) return ''
  if (summary.failures > 0) return `${summary.failures} blocking item(s) to clear`
  if (summary.warnings > 0) return `${summary.warnings} item(s) need a closer look`
  return 'No blocking issues found'
})

const headlineColor = computed(() => {
  const summary = checklist.value?.summary
  if (!summary) return 'blue-grey-6'
  if (summary.failures > 0) return 'negative'
  if (summary.warnings > 0) return 'warning'
  return 'positive'
})
</script>

<template>
  <q-card v-if="checklist" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="fact_check" size="18px" class="q-mr-xs" />Due-diligence checklist
        <q-icon name="info" size="14px" class="q-ml-xs lot-text-faint" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          Auto-populated from this parcel's zoning, liens, L&I, flood, ownership, valuation, and
          deal signals. Informational — confirm each with the city and your own advisors.
        </q-tooltip>
        <q-space />
        <q-chip dense square :color="headlineColor" text-color="white" icon="rule">
          {{ checklist.summary.passed }} clear<template v-if="checklist.summary.not_evaluated">
            · {{ checklist.summary.not_evaluated }} not checked</template
          >
        </q-chip>
      </div>

      <div class="text-body2 text-weight-medium q-mb-sm" :class="`text-${headlineColor}`">
        {{ headline }}
      </div>

      <div class="check-list">
        <div v-for="item in checklist.items" :key="item.code" class="check-row">
          <q-icon
            :name="styleFor(item).icon"
            :color="styleFor(item).color"
            size="20px"
            class="check-icon"
          />
          <div class="check-body">
            <div class="check-cat" data-test="check-label">{{ item.label }}</div>
            <div class="check-detail">{{ item.detail }}</div>
          </div>
        </div>
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
.check-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.check-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.check-icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.check-body {
  min-width: 0;
}
.check-cat {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--lot-ink);
}
.check-detail {
  font-size: 12px;
  color: var(--lot-muted);
  line-height: 1.3;
}
</style>
