<script setup lang="ts">
import { computed } from 'vue'

import {
  formatCurrency,
  formatFeet,
  formatPercent,
  formatRange,
  formatSqft,
  scoreColor,
  scoreLabel,
  severityColor,
  severityIcon,
} from '@/lib/format'
import type { VerdictResult } from '@/lib/types'

const props = defineProps<{ verdict: VerdictResult }>()

interface Status {
  label: string
  color: string
  icon: string
}

const SOURCE_LABELS: Record<string, string> = {
  li_event: 'Source: L&I (Licenses & Inspections)',
  tax_status: 'Source: Dept. of Revenue tax records',
  flood_zone: 'Source: FEMA flood maps',
  parcel: 'Source: OPA / city parcel records',
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? `Source: ${source}`
}

const SEVERITY_HINT: Record<string, string> = {
  high: 'High severity — a likely deal-killer; verify before proceeding.',
  medium: 'Medium severity — material; factor it into price and plan.',
  low: 'Low severity — worth noting, usually manageable.',
  info: 'Informational — context, not necessarily a problem.',
}

function severityHint(severity: string): string {
  return SEVERITY_HINT[severity] ?? ''
}

const hasValueEstimate = computed(
  () => props.verdict.value_estimate_low != null || props.verdict.value_estimate_high != null,
)

const SCORE_HEX: Record<string, string> = {
  positive: '#2e7d32',
  'amber-8': '#ef6c00',
  negative: '#c62828',
  grey: '#9e9e9e',
}
const scoreHex = computed(() => SCORE_HEX[scoreColor(props.verdict.opportunity_score)] ?? '#9e9e9e')

const SEVERITY_HEX: Record<string, string> = {
  high: '#c62828',
  medium: '#f9a825',
  low: '#90a4ae',
  info: '#0277bd',
}
function severityHex(severity: string): string {
  return SEVERITY_HEX[severity] ?? '#90a4ae'
}

const buildStatus = computed<Status>(() => {
  const v = props.verdict
  if (v.summary?.toLowerCase().includes('master plan')) {
    return { label: 'Master plan required', color: 'blue-grey-6', icon: 'account_balance' }
  }
  if (v.can_build_by_right) {
    return { label: 'Buildable by-right', color: 'positive', icon: 'check_circle' }
  }
  if (v.needs_variance) {
    return { label: 'Variance likely', color: 'warning', icon: 'gavel' }
  }
  return { label: 'Buildability uncertain', color: 'grey-6', icon: 'help_outline' }
})
</script>

<template>
  <q-card flat bordered class="rounded-borders">
    <q-card-section
      class="row items-center no-wrap q-pb-sm score-head"
      :style="{ '--accent': scoreHex }"
    >
      <q-circular-progress
        show-value
        :value="verdict.opportunity_score"
        :min="0"
        :max="100"
        size="74px"
        :thickness="0.22"
        :color="scoreColor(verdict.opportunity_score)"
        track-color="grey-3"
        class="q-mr-md"
      >
        <span class="text-h6 text-weight-bold">{{ Math.round(verdict.opportunity_score) }}</span>
      </q-circular-progress>
      <div class="col">
        <div class="text-overline text-grey-7 row items-center no-wrap">
          Opportunity score
          <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
          <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
            A 0–100 blend of buildability (60%) and low risk (40%). Higher means more upside with
            fewer obstacles. Informational, not advice.
          </q-tooltip>
        </div>
        <div class="text-h6" :class="`text-${scoreColor(verdict.opportunity_score)}`">
          {{ scoreLabel(verdict.opportunity_score) }}
        </div>
        <div class="text-body2 text-grey-8 summary-text">{{ verdict.summary }}</div>
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="architecture" size="18px" class="q-mr-xs" />Buildability
      </div>
      <q-chip dense square :color="buildStatus.color" text-color="white" :icon="buildStatus.icon">
        {{ buildStatus.label }}
        <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
          Whether the lot can be developed under Title 14 without a zoning variance. "Variance
          likely" means a board (ZBA) approval would be needed.
        </q-tooltip>
      </q-chip>
      <div class="row q-col-gutter-sm q-mt-xs">
        <div class="col-4 stat">
          <div class="stat-label">By-right units</div>
          <div class="stat-value">{{ verdict.by_right_units ?? '—' }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Dwelling units allowed by-right (no variance) under the lot's zoning district.
          </q-tooltip>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Max height</div>
          <div class="stat-value">{{ formatFeet(verdict.max_height_ft) }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Maximum by-right building height for the district. Drives the 3D envelope.
          </q-tooltip>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Buildable area</div>
          <div class="stat-value">{{ formatSqft(verdict.buildable_area_sqft) }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Estimated footprint after required setbacks. Approximate.
          </q-tooltip>
        </div>
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="payments" size="18px" class="q-mr-xs" />Estimated land value
      </div>
      <template v-if="hasValueEstimate">
        <div class="text-h6 text-primary">
          {{ formatRange(verdict.value_estimate_low, verdict.value_estimate_high) }}
        </div>
        <div class="row q-col-gutter-sm q-mt-xs">
          <div class="col-6 stat">
            <div class="stat-label">Confidence</div>
            <div class="stat-value">{{ formatPercent(verdict.value_confidence) }}</div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              How tightly recent comparable sales agree. Lower confidence means thin or scattered
              comps.
            </q-tooltip>
          </div>
          <div class="col-6 stat">
            <div class="stat-label">vs. assessment</div>
            <div class="stat-value">{{ formatCurrency(verdict.assessment_market_gap) }}</div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Estimated market value minus the OPA assessed value. A large gap can signal an
              over- or under-assessment (tax-appeal angle).
            </q-tooltip>
          </div>
        </div>
      </template>
      <div v-else class="empty-value">
        <q-icon name="search_off" size="18px" class="q-mr-xs text-grey-5" />
        Not enough recorded comparable sales nearby to estimate a land value yet.
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="warning_amber" size="18px" class="q-mr-xs" />Risk
        <q-space />
        <q-chip
          dense
          square
          :color="
            (verdict.risk_score ?? 0) >= 50
              ? 'negative'
              : (verdict.risk_score ?? 0) >= 20
                ? 'warning'
                : 'positive'
          "
          text-color="white"
        >
          {{ verdict.risk_score == null ? '—' : Math.round(verdict.risk_score) }}/100
          <q-tooltip max-width="260px" anchor="top middle" self="bottom middle">
            0–100 from the flags below (tax liens, L&I, flood, ownership). Higher is riskier;
            0 means no major flags found.
          </q-tooltip>
        </q-chip>
      </div>
      <div v-if="verdict.risk_flags.length" class="flag-list q-mt-xs">
        <div
          v-for="flag in verdict.risk_flags"
          :key="flag.code"
          class="flag"
          :style="{ '--bar': severityHex(flag.severity) }"
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
          </div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            {{ severityHint(flag.severity) }} · {{ sourceLabel(flag.source) }}
          </q-tooltip>
        </div>
      </div>
      <div v-else class="no-flags">
        <q-icon name="verified" size="18px" color="positive" class="q-mr-xs" />
        No major risk flags found.
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.rounded-borders {
  border-radius: var(--lot-radius) !important;
  box-shadow: var(--lot-shadow);
}
.score-head {
  border-left: 4px solid var(--accent);
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
.summary-text {
  white-space: normal;
  line-height: 1.35;
  margin-top: 2px;
}
.stat {
  text-align: center;
  border-radius: var(--lot-radius-sm);
  padding: 6px 4px;
  background: #f6f8fb;
}
.stat-label {
  font-size: 11px;
  color: #78909c;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.stat-value {
  font-size: 15px;
  font-weight: 700;
  color: #1f2933;
}
.flag-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.flag {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 9px 11px;
  border-radius: var(--lot-radius-sm);
  background: #f8fafc;
  border-left: 3px solid var(--bar);
}
.flag-icon {
  margin-top: 1px;
}
.flag-body {
  min-width: 0;
}
.flag-title {
  font-weight: 600;
  font-size: 13px;
  color: #1f2933;
  line-height: 1.25;
}
.flag-detail {
  white-space: normal;
  line-height: 1.35;
  font-size: 12px;
  color: #5b6b7d;
  margin-top: 1px;
}
.no-flags {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #5b6b7d;
}
.empty-value {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: #78909c;
  line-height: 1.35;
}
</style>
