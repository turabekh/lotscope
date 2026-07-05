<script setup lang="ts">
import { computed } from 'vue'

import VarianceOutlookLine from '@/components/VarianceOutlookLine.vue'
import {
  formatCurrency,
  formatFeet,
  formatPercent,
  formatRange,
  formatSqft,
  severityColor,
  severityIcon,
  severityVar,
} from '@/lib/format'
import type { VerdictResult } from '@/lib/types'

const props = defineProps<{ verdict: VerdictResult; developed?: boolean }>()

interface Status {
  label: string
  color: string
  icon: string
}

const SOURCE_LABELS: Record<string, string> = {
  li_event: 'Source: L&I (Licenses & Inspections)',
  tax_status: 'Source: Dept. of Revenue tax records',
  flood_zone: 'Source: FEMA flood maps',
  historicdistricts_local: 'Source: Philadelphia historic districts',
  street_centerline: 'Source: city street centerlines',
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

const riskTone = computed(() => {
  const score = props.verdict.risk_score ?? 0
  return score >= 50 ? 'negative' : score >= 20 ? 'warning' : 'positive'
})

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
  <q-card flat bordered class="lot-card">
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
      <div v-if="developed" class="redev-note">
        Redevelopment scenario — assumes the existing structure is removed.
      </div>
      <div class="row q-col-gutter-sm q-mt-xs">
        <div class="col-4 stat">
          <div class="stat-label">By-right units</div>
          <div class="stat-value lot-numeric">{{ verdict.by_right_units ?? '—' }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Dwelling units allowed by-right (no variance) under the lot's zoning district.
          </q-tooltip>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Max height</div>
          <div class="stat-value lot-numeric">{{ formatFeet(verdict.max_height_ft) }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Maximum by-right building height for the district. Drives the 3D envelope.
          </q-tooltip>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Buildable area</div>
          <div class="stat-value lot-numeric">{{ formatSqft(verdict.buildable_area_sqft) }}</div>
          <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
            Estimated footprint after required setbacks. Approximate.
          </q-tooltip>
        </div>
      </div>
      <VarianceOutlookLine
        v-if="verdict.needs_variance"
        :parcel-number="verdict.parcel_number"
      />
    </q-card-section>

    <q-separator />

    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="payments" size="18px" class="q-mr-xs" />{{
          developed ? 'Redevelopment land value' : 'Estimated land value'
        }}
      </div>
      <template v-if="hasValueEstimate">
        <div class="value-figure lot-numeric">
          {{ formatRange(verdict.value_estimate_low, verdict.value_estimate_high) }}
        </div>
        <div class="row q-col-gutter-sm q-mt-xs">
          <div class="stat" :class="developed ? 'col-12' : 'col-6'">
            <div class="stat-label">Confidence</div>
            <div class="stat-value lot-numeric">{{ formatPercent(verdict.value_confidence) }}</div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              How tightly recent comparable sales agree. Lower confidence means thin or scattered
              comps.
            </q-tooltip>
          </div>
          <div v-if="!developed" class="col-6 stat">
            <div class="stat-label">vs. assessment</div>
            <div class="stat-value lot-numeric">
              {{ formatCurrency(verdict.assessment_market_gap) }}
            </div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              Estimated market value minus the OPA assessed value. A large gap can signal an
              over- or under-assessment (tax-appeal angle).
            </q-tooltip>
          </div>
        </div>
      </template>
      <div v-else class="empty-value">
        <q-icon name="search_off" size="18px" class="q-mr-xs" />
        Not enough recorded comparable sales nearby to estimate a land value yet.
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="warning_amber" size="18px" class="q-mr-xs" />Risk
        <q-space />
        <q-chip dense square :color="riskTone" text-color="white">
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
          :style="{ '--bar': severityVar(flag.severity) }"
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
.value-figure {
  font-size: 18px;
  font-weight: 700;
  color: var(--lot-accent-ink);
}
.redev-note {
  font-size: 11.5px;
  color: var(--lot-faint);
  margin-top: 4px;
  line-height: 1.35;
}
.stat {
  text-align: center;
  border-radius: var(--lot-radius-sm);
  padding: 6px 4px;
  background: var(--lot-surface-2);
}
.stat-label {
  font-size: 11px;
  color: var(--lot-faint);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.stat-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--lot-ink);
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
  background: var(--lot-surface-2);
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
  color: var(--lot-ink);
  line-height: 1.25;
}
.flag-detail {
  white-space: normal;
  line-height: 1.35;
  font-size: 12px;
  color: var(--lot-muted);
  margin-top: 1px;
}
.no-flags {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--lot-muted);
}
.empty-value {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--lot-faint);
  line-height: 1.35;
}
</style>
