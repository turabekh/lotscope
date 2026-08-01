<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { severityColor, severityIcon, severityVar } from '@/lib/format'
import type { RiskFlag } from '@/lib/types'
import { severityHint, sourceLabel } from '@/lib/verdict-explain'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { verdict } = storeToRefs(store)

const SEVERITY_ORDER = ['high', 'medium', 'low', 'info']

type FlagGroup = { severity: string; heading: string; flags: RiskFlag[] }

const GROUP_HEADING: Record<string, string> = {
  high: 'Deal killers',
  medium: 'Needs attention',
  low: 'Worth knowing',
  info: 'Context',
}

const flags = computed<RiskFlag[]>(() => verdict.value?.risk_flags ?? [])

const groups = computed<FlagGroup[]>(() =>
  SEVERITY_ORDER.map((severity) => ({
    severity,
    heading: GROUP_HEADING[severity] ?? 'Other',
    flags: flags.value.filter((flag) => flag.severity === severity),
  })).filter((group) => group.flags.length > 0),
)

const score = computed(() => verdict.value?.risk_score ?? null)

const scoreTone = computed(() => {
  const value = score.value
  if (value === null) return 'grey-7'
  if (value >= 60) return 'negative'
  if (value >= 30) return 'warning'
  return 'positive'
})

const summary = computed(() => {
  const count = flags.value.length
  if (count === 0) return 'No risk flags recorded for this lot.'
  const noun = count === 1 ? 'flag' : 'flags'
  const worst = groups.value[0]
  if (worst?.severity === 'high') {
    return `${count} ${noun} recorded, including at least one that can kill a deal.`
  }
  return `${count} ${noun} recorded. None are deal killers, but review them before committing.`
})
</script>

<template>
  <q-card flat bordered class="rounded-borders" data-test="risk-panel">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="warning_amber" size="18px" class="q-mr-xs" />Risk
        <q-space />
        <q-chip dense square :color="scoreTone" text-color="white" data-test="risk-panel-score">
          {{ score === null ? '—' : Math.round(score) }}/100
          <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
            0–100 from the flags below (tax liens, L&amp;I, flood, ownership). Higher is riskier; 0
            means no major flags found.
          </q-tooltip>
        </q-chip>
      </div>

      <div v-if="!verdict" class="risk-empty" data-test="risk-panel-no-verdict">
        <q-icon name="hourglass_empty" size="20px" />
        <span>No verdict computed yet, so no risk review has run on this lot.</span>
      </div>

      <template v-else>
        <div class="risk-summary" data-test="risk-panel-summary">{{ summary }}</div>

        <div v-if="flags.length === 0" class="risk-clear" data-test="risk-panel-clear">
          <q-icon name="verified_user" size="20px" color="positive" />
          <span>
            Nothing was found in liens, L&amp;I, flood, or ownership records. That is what we
            checked — it is not a guarantee the lot is clean.
          </span>
        </div>

        <div v-for="group in groups" :key="group.severity" class="flag-group">
          <div class="group-heading">
            {{ group.heading }}
            <span class="group-count">{{ group.flags.length }}</span>
          </div>
          <div
            v-for="flag in group.flags"
            :key="flag.code"
            class="flag"
            :style="{ '--bar': severityVar(flag.severity) }"
            data-test="risk-panel-flag"
          >
            <q-icon
              :name="severityIcon(flag.severity)"
              :color="severityColor(flag.severity)"
              size="19px"
              class="flag-icon"
            />
            <div class="flag-body">
              <div class="flag-title">{{ flag.label }}</div>
              <div class="flag-detail">{{ flag.detail }}</div>
              <div class="flag-source">
                {{ severityHint(flag.severity) }} · {{ sourceLabel(flag.source) }}
              </div>
            </div>
          </div>
        </div>
      </template>
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
.risk-summary {
  font-size: 13px;
  font-weight: 600;
  color: var(--lot-ink);
  margin-bottom: 8px;
}
.risk-empty,
.risk-clear {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--lot-muted);
}
.flag-group + .flag-group {
  margin-top: 10px;
}
.group-heading {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-faint);
  margin: 8px 0 4px;
}
.group-count {
  font-weight: 700;
  color: var(--lot-muted);
}
.flag {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
  border-left: 3px solid var(--bar);
}
.flag + .flag {
  margin-top: 6px;
}
.flag-icon {
  margin-top: 1px;
}
.flag-body {
  min-width: 0;
  flex: 1;
}
.flag-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--lot-ink);
}
.flag-detail {
  font-size: 12px;
  color: var(--lot-muted);
  line-height: 1.4;
}
.flag-source {
  font-size: 11px;
  color: var(--lot-faint);
  margin-top: 3px;
}
</style>
