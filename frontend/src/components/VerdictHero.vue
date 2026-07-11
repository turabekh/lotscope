<script setup lang="ts">
import { computed } from 'vue'

import { formatRange, marketCodeFromParcelNumber, scoreLabel, scoreVar } from '@/lib/format'
import type { VerdictResult } from '@/lib/types'
import { useMarketStore } from '@/stores/market'

const props = defineProps<{ verdict: VerdictResult; developed?: boolean }>()
const emit = defineEmits<{ explain: [] }>()

const market = useMarketStore()

interface Pillar {
  key: string
  label: string
  value: string
  icon: string
  tone: 'positive' | 'warning' | 'neutral' | 'caution'
  hint: string
}

const buildPillar = computed<Pillar>(() => {
  const v = props.verdict
  if (v.summary?.toLowerCase().includes('master plan')) {
    return {
      key: 'build',
      label: 'Buildability',
      value: 'Master plan',
      icon: 'account_balance',
      tone: 'neutral',
      hint: 'A civic/special-purpose district — a master plan or approval is required.',
    }
  }
  if (v.can_build_by_right) {
    return {
      key: 'build',
      label: 'Buildability',
      value: v.by_right_units ? `By-right · ${v.by_right_units} unit${v.by_right_units > 1 ? 's' : ''}` : 'By-right',
      icon: 'check_circle',
      tone: 'positive',
      hint: 'Developable under Title 14 with no zoning variance.',
    }
  }
  if (v.needs_variance) {
    return {
      key: 'build',
      label: 'Buildability',
      value: 'Variance likely',
      icon: 'gavel',
      tone: 'warning',
      hint: 'A zoning variance or special exception is likely required.',
    }
  }
  return {
    key: 'build',
    label: 'Buildability',
    value: 'Uncertain',
    icon: 'help_outline',
    tone: 'neutral',
    hint: 'Zoning conformance could not be resolved for this parcel.',
  }
})

const valuePillar = computed<Pillar>(() => {
  const v = props.verdict
  const has = v.value_estimate_low != null && v.value_estimate_high != null
  return {
    key: 'value',
    label: props.developed ? 'Redev. land value' : 'Est. land value',
    value: has ? formatRange(v.value_estimate_low, v.value_estimate_high) : 'No comps',
    icon: 'payments',
    tone: 'neutral',
    hint: props.developed
      ? 'Hypothetical land value for a teardown or redevelopment — not this property’s current improved value.'
      : has
        ? 'Estimated from recent recorded comparable sales nearby.'
        : 'Not enough recorded comparable sales nearby yet.',
  }
})

const riskPillar = computed<Pillar>(() => {
  const score = props.verdict.risk_score
  const count = props.verdict.risk_flags.length
  const coverageNote = market.infoByCode(
    marketCodeFromParcelNumber(props.verdict.parcel_number),
  )?.risk_coverage_note
  const tone: Pillar['tone'] =
    score == null ? 'neutral' : score >= 50 ? 'caution' : score >= 20 ? 'warning' : 'positive'
  const cleanHint = coverageNote
    ? `No major risk flags found ${coverageNote} — absent feeds mean this is not a proven clean result.`
    : 'No major risk flags found.'
  return {
    key: 'risk',
    label: 'Risk',
    value: score == null ? '—' : `${Math.round(score)}/100`,
    icon: count > 0 ? 'warning_amber' : 'verified',
    tone,
    hint:
      count > 0
        ? `${count} flag${count > 1 ? 's' : ''} — see the Verdict tab. Higher score is riskier.`
        : cleanHint,
  }
})

const pillars = computed(() => [buildPillar.value, valuePillar.value, riskPillar.value])
const accent = computed(() => scoreVar(props.verdict.opportunity_score))
</script>

<template>
  <div class="hero lot-card" :style="{ '--accent': accent }">
    <div class="hero-top">
      <q-circular-progress
        :value="verdict.opportunity_score"
        :min="0"
        :max="100"
        size="78px"
        :thickness="0.18"
        color="grey"
        track-color="grey-3"
        class="gauge"
      >
        <span class="gauge-num lot-numeric">{{ Math.round(verdict.opportunity_score) }}</span>
      </q-circular-progress>

      <div class="hero-headline">
        <div class="hero-overline">
          Opportunity score
          <q-icon name="info" size="13px" class="hero-info" />
          <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
            A 0–100 blend of buildability (60%) and low risk (40%). Higher means more upside with
            fewer obstacles. Informational, not advice.
          </q-tooltip>
        </div>
        <div class="hero-label">{{ scoreLabel(verdict.opportunity_score) }}</div>
        <div class="hero-summary">{{ verdict.summary }}</div>
        <button type="button" class="why-link" @click="emit('explain')">Why this score?</button>
      </div>
    </div>

    <div class="pillars">
      <div v-for="pillar in pillars" :key="pillar.key" class="pillar" :class="pillar.tone">
        <q-icon :name="pillar.icon" size="18px" class="pillar-icon" />
        <div class="pillar-text">
          <div class="pillar-label">{{ pillar.label }}</div>
          <div class="pillar-value lot-numeric">{{ pillar.value }}</div>
        </div>
        <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">{{ pillar.hint }}</q-tooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero {
  padding: 16px;
  border-top: 3px solid var(--accent);
}
.hero-top {
  display: flex;
  align-items: center;
  gap: 14px;
}
.gauge {
  color: var(--accent);
  flex: 0 0 auto;
}
.gauge :deep(.q-circular-progress__circle) {
  color: var(--accent);
}
.gauge-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--lot-ink);
}
.hero-headline {
  min-width: 0;
}
.hero-overline {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--lot-faint);
}
.hero-info {
  color: var(--lot-faint);
}
.hero-label {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1.2;
  margin-top: 1px;
}
.hero-summary {
  font-size: 12.5px;
  color: var(--lot-muted);
  line-height: 1.35;
  margin-top: 3px;
}
.why-link {
  margin-top: 6px;
  padding: 0;
  border: none;
  background: none;
  font-size: 12px;
  font-weight: 600;
  color: var(--q-primary);
  cursor: pointer;
}
.why-link:hover {
  text-decoration: underline;
}
.pillars {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 14px;
}
.pillar {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 9px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2);
  border: 1px solid var(--lot-border);
}
.pillar-icon {
  color: var(--lot-faint);
  flex: 0 0 auto;
}
.pillar.positive .pillar-icon {
  color: var(--lot-score-positive);
}
.pillar.warning .pillar-icon {
  color: var(--lot-sev-medium);
}
.pillar.caution .pillar-icon {
  color: var(--lot-score-caution);
}
.pillar-text {
  min-width: 0;
}
.pillar-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--lot-faint);
  line-height: 1.2;
}
.pillar-value {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--lot-ink);
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
