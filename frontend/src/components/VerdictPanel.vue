<script setup lang="ts">
import { formatCurrency, formatRange } from '@/lib/format'
import type { VerdictResult } from '@/lib/types'

defineProps<{ verdict: VerdictResult }>()

const severityColor: Record<string, string> = {
  high: 'negative',
  medium: 'warning',
  low: 'grey',
  info: 'info',
}

function yesNo(value: boolean | null): string {
  if (value === null) return '—'
  return value ? 'yes' : 'no'
}
</script>

<template>
  <q-card flat bordered class="q-mb-md">
    <q-card-section>
      <div class="row items-center justify-between">
        <div class="text-h6">Parcel Verdict</div>
        <q-chip
          :label="`Opportunity ${verdict.opportunity_score.toFixed(0)}`"
          color="primary"
          text-color="white"
        />
      </div>
      <div class="text-body2 text-grey-8 q-mt-sm">{{ verdict.summary }}</div>
    </q-card-section>
    <q-separator />
    <q-card-section class="row q-col-gutter-md">
      <div class="col-12 col-sm-4">
        <div class="text-caption text-grey">Build</div>
        <div>By-right: {{ yesNo(verdict.can_build_by_right) }}</div>
        <div>Units: {{ verdict.by_right_units ?? '—' }}</div>
        <div>Variance: {{ yesNo(verdict.needs_variance) }}</div>
      </div>
      <div class="col-12 col-sm-4">
        <div class="text-caption text-grey">Value</div>
        <div>{{ formatRange(verdict.value_estimate_low, verdict.value_estimate_high) }}</div>
        <div>Assessment gap: {{ formatCurrency(verdict.assessment_market_gap) }}</div>
      </div>
      <div class="col-12 col-sm-4">
        <div class="text-caption text-grey">Risk</div>
        <div>Score: {{ verdict.risk_score ?? '—' }}</div>
        <div class="q-gutter-xs q-mt-xs">
          <q-chip
            v-for="flag in verdict.risk_flags"
            :key="flag.code"
            dense
            :color="severityColor[flag.severity] ?? 'grey'"
            text-color="white"
            :label="flag.label"
          />
        </div>
      </div>
    </q-card-section>
  </q-card>
</template>
