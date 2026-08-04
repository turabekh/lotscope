<script setup lang="ts">
import { computed } from 'vue'

import { buildQualifier, postureDisplay, resolvePosture } from '@/lib/by-right'
import { formatRange, marketCodeFromParcelNumber, scoreVar } from '@/lib/format'
import { screeningDisplay } from '@/lib/screening'
import { rankedDealKillers } from '@/lib/deal-killers'
import type { ParcelChecklist, VerdictResult } from '@/lib/types'
import { useMarketStore } from '@/stores/market'

const props = defineProps<{
  verdict: VerdictResult
  developed?: boolean
  checklist?: ParcelChecklist | null
}>()
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

const posture = computed(() => resolvePosture(props.verdict, props.checklist))

const buildPillar = computed<Pillar>(() => {
  const display = postureDisplay(posture.value)
  const units = props.verdict.by_right_units
  const value =
    posture.value === 'by_right' && units
      ? `Base district · ${units} unit${units > 1 ? 's' : ''}`
      : display.label
  return {
    key: 'build',
    label: 'Buildability',
    value,
    icon: display.icon,
    tone: display.tone,
    hint: buildQualifier(posture.value, props.checklist ?? null),
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
const screening = computed(() => screeningDisplay(props.verdict.recommendation))
const dealKillers = computed(() => rankedDealKillers(props.verdict.risk_flags))
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
          Screening result
          <q-icon name="info" size="13px" class="hero-info" />
          <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
            A preliminary screening result from deterministic rules over the parcel's own data.
            Informational only — it is not investment advice or a professional determination.
          </q-tooltip>
        </div>
        <div v-if="screening" class="hero-label" :class="`text-${screening.tone}`">
          <q-icon :name="screening.icon" size="20px" class="q-mr-xs" />{{ screening.label }}
        </div>
        <div v-else class="hero-label text-grey-6" data-test="no-recommendation">
          Not yet screened
        </div>
        <div class="hero-summary">
          {{ verdict.recommendation_reason ?? verdict.summary }}
        </div>
        <div v-if="dealKillers.length" class="killers" data-test="deal-killers">
          <q-chip
            v-for="flag in dealKillers"
            :key="flag.code"
            dense
            square
            outline
            :color="flag.severity === 'high' ? 'negative' : 'warning'"
            icon="report_problem"
          >
            {{ flag.label }}
          </q-chip>
        </div>
        <button type="button" class="why-link" @click="emit('explain')">
          Why this result? · Opportunity score {{ Math.round(verdict.opportunity_score) }}
        </button>
      </div>
    </div>

    <div class="pillars">
      <div v-for="pillar in pillars" :key="pillar.key" class="pillar" :class="pillar.tone">
        <q-icon :name="pillar.icon" size="18px" class="pillar-icon" />
        <div class="pillar-text">
          <div class="pillar-label">{{ pillar.label }}</div>
          <div class="pillar-value lot-numeric">{{ pillar.value }}</div>
          <div class="pillar-hint">{{ pillar.hint }}</div>
        </div>
        <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">{{
          pillar.hint
        }}</q-tooltip>
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
.killers {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.pillars {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 14px;
}
.pillar-hint {
  display: none;
}
@media (max-width: 1023px) {
  .pillars {
    grid-template-columns: 1fr;
  }
  .pillar {
    align-items: flex-start;
  }
  .pillar-value {
    white-space: normal;
  }
  .pillar-hint {
    display: block;
    margin-top: 3px;
    font-size: 11px;
    line-height: 1.3;
    color: var(--lot-faint);
  }
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
