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
    <q-card-section class="row items-center no-wrap q-pb-sm">
      <q-circular-progress
        :value="verdict.opportunity_score"
        size="74px"
        :thickness="0.18"
        :color="scoreColor(verdict.opportunity_score)"
        track-color="grey-3"
        class="q-mr-md"
      >
        <span class="text-h6 text-weight-bold">{{ Math.round(verdict.opportunity_score) }}</span>
      </q-circular-progress>
      <div class="col">
        <div class="text-overline text-grey-7">Opportunity score</div>
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
      </q-chip>
      <div class="row q-col-gutter-sm q-mt-xs">
        <div class="col-4 stat">
          <div class="stat-label">By-right units</div>
          <div class="stat-value">{{ verdict.by_right_units ?? '—' }}</div>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Max height</div>
          <div class="stat-value">{{ formatFeet(verdict.max_height_ft) }}</div>
        </div>
        <div class="col-4 stat">
          <div class="stat-label">Buildable area</div>
          <div class="stat-value">{{ formatSqft(verdict.buildable_area_sqft) }}</div>
        </div>
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="payments" size="18px" class="q-mr-xs" />Estimated land value
      </div>
      <div class="text-h6 text-primary">
        {{ formatRange(verdict.value_estimate_low, verdict.value_estimate_high) }}
      </div>
      <div class="row q-col-gutter-sm q-mt-xs">
        <div class="col-6 stat">
          <div class="stat-label">Confidence</div>
          <div class="stat-value">{{ formatPercent(verdict.value_confidence) }}</div>
        </div>
        <div class="col-6 stat">
          <div class="stat-label">vs. assessment</div>
          <div class="stat-value">{{ formatCurrency(verdict.assessment_market_gap) }}</div>
        </div>
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
        </q-chip>
      </div>
      <div v-if="verdict.risk_flags.length" class="q-mt-xs">
        <q-list separator dense>
          <q-item v-for="flag in verdict.risk_flags" :key="flag.code" class="q-px-none">
            <q-item-section avatar top class="q-pr-sm" style="min-width: 32px">
              <q-icon :name="severityIcon(flag.severity)" :color="severityColor(flag.severity)" />
            </q-item-section>
            <q-item-section>
              <q-item-label class="text-weight-medium">{{ flag.label }}</q-item-label>
              <q-item-label caption class="flag-detail">{{ flag.detail }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
      <div v-else class="text-body2 text-grey-6 q-mt-xs">No major risk flags.</div>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.section-title {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #455a64;
  margin-bottom: 6px;
}
.summary-text {
  white-space: normal;
  line-height: 1.35;
  margin-top: 2px;
}
.stat {
  text-align: center;
}
.stat-label {
  font-size: 11px;
  color: #78909c;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #263238;
}
.flag-detail {
  white-space: normal;
  line-height: 1.35;
}
</style>
