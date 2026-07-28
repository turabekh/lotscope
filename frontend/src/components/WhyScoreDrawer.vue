<script setup lang="ts">
import { computed } from 'vue'

import {
  formatCurrency,
  formatFeet,
  formatPercent,
  formatRange,
  severityColor,
  severityIcon,
} from '@/lib/format'
import type { VerdictResult } from '@/lib/types'
import { flagWeight, scoreBreakdown, severityHint, sourceLabel } from '@/lib/verdict-explain'

const props = defineProps<{ modelValue: boolean; verdict: VerdictResult }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const breakdown = computed(() => scoreBreakdown(props.verdict))

const flags = computed(() =>
  [...props.verdict.risk_flags].sort((a, b) => flagWeight(b.severity) - flagWeight(a.severity)),
)

const sourceNames = computed(() => {
  const names = new Set<string>()
  for (const entry of props.verdict.sources) {
    const dimension = entry as { sources?: { source?: string }[] }
    for (const source of dimension.sources ?? []) {
      if (source.source) names.add(sourceLabel(source.source))
    }
  }
  return [...names].sort()
})

const computedAtLabel = computed(() =>
  props.verdict.computed_at ? new Date(props.verdict.computed_at).toLocaleString() : '—',
)
</script>

<template>
  <q-dialog v-model="open" position="right" full-height>
    <q-card class="why-card">
      <div class="why-head">
        <q-icon name="insights" size="18px" class="q-mr-sm" />
        <span class="why-title">Why this score?</span>
        <q-space />
        <q-btn flat dense round size="sm" icon="close" aria-label="Close" @click="open = false" />
      </div>

      <q-scroll-area class="why-body">
        <div class="q-pa-md">
          <section class="why-section">
            <div class="section-label">Opportunity score</div>
            <div class="formula">
              60% buildability + 40% low-risk =
              <b>{{ breakdown.total }}</b>
            </div>
            <div class="term">
              <span>Buildability</span>
              <span class="term-calc">
                {{ breakdown.buildability ?? 'not scored' }} × 0.6 =
                <b>{{ breakdown.buildabilityTerm }}</b>
              </span>
            </div>
            <q-linear-progress
              :value="breakdown.buildabilityTerm / 100"
              color="teal"
              class="term-bar"
              rounded
            />
            <div class="term">
              <span>Low risk</span>
              <span class="term-calc">
                (100 − {{ breakdown.risk ?? 0 }}) × 0.4 = <b>{{ breakdown.riskTerm }}</b>
              </span>
            </div>
            <q-linear-progress
              :value="breakdown.riskTerm / 100"
              color="indigo"
              class="term-bar"
              rounded
            />
          </section>

          <section class="why-section">
            <div class="section-label">Buildability</div>
            <ul class="facts">
              <li>
                By-right:
                <b>{{
                  verdict.can_build_by_right === null
                    ? 'unresolved'
                    : verdict.can_build_by_right
                      ? 'yes'
                      : 'no'
                }}</b>
              </li>
              <li v-if="verdict.by_right_units !== null">
                By-right units: <b>{{ verdict.by_right_units }}</b>
              </li>
              <li v-if="verdict.max_height_ft !== null">
                Max height: <b>{{ formatFeet(verdict.max_height_ft) }}</b>
              </li>
              <li v-if="verdict.needs_variance !== null">
                Variance likely: <b>{{ verdict.needs_variance ? 'yes' : 'no' }}</b>
              </li>
            </ul>
            <div class="section-note">{{ verdict.summary }}</div>
          </section>

          <section class="why-section">
            <div class="section-label">
              Risk
              <span class="section-sub">score {{ verdict.risk_score ?? 'n/a' }}</span>
            </div>
            <div v-if="flags.length === 0" class="section-note">No risk flags on record.</div>
            <div v-for="flag in flags" :key="flag.code" class="flag">
              <q-icon
                :name="severityIcon(flag.severity)"
                :color="severityColor(flag.severity)"
                size="18px"
              />
              <div class="flag-body">
                <div class="flag-title">
                  {{ flag.label }}
                  <span class="flag-weight">+{{ flagWeight(flag.severity) }}</span>
                </div>
                <div class="flag-detail">{{ flag.detail }}</div>
                <div class="flag-source">Source: {{ sourceLabel(flag.source) }}</div>
                <q-tooltip>{{ severityHint(flag.severity) }}</q-tooltip>
              </div>
            </div>
          </section>

          <section
            v-if="verdict.value_estimate_low !== null || verdict.value_estimate_high !== null"
            class="why-section"
          >
            <div class="section-label">Estimated value</div>
            <ul class="facts">
              <li>
                Range:
                <b>{{ formatRange(verdict.value_estimate_low, verdict.value_estimate_high) }}</b>
              </li>
              <li v-if="verdict.value_confidence !== null">
                Confidence: <b>{{ formatPercent(verdict.value_confidence) }}</b>
              </li>
              <li v-if="verdict.assessment_market_gap !== null">
                Assessment gap: <b>{{ formatCurrency(verdict.assessment_market_gap) }}</b>
              </li>
            </ul>
          </section>

          <section class="why-section provenance">
            <div class="section-label">Provenance</div>
            <div class="prov-line">
              Version: <b>{{ verdict.verdict_version }}</b>
            </div>
            <div class="prov-line">
              Computed: <b>{{ computedAtLabel }}</b>
            </div>
            <div v-if="sourceNames.length" class="prov-line">
              Sources: {{ sourceNames.join(' · ') }}
            </div>
            <div class="prov-note">
              Informational only — not legal, financial, or real-estate advice.
            </div>
          </section>
        </div>
      </q-scroll-area>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.why-card {
  width: 400px;
  max-width: 92vw;
  display: flex;
  flex-direction: column;
}
.why-head {
  display: flex;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid var(--lot-border);
}
.why-title {
  font-weight: 700;
}
.why-body {
  flex: 1;
}
.why-section {
  padding: 12px 0;
  border-bottom: 1px solid var(--lot-border);
}
.why-section:last-child {
  border-bottom: none;
}
.section-label {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.section-sub {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  color: var(--lot-faint);
  margin-left: 6px;
}
.formula {
  font-size: 14px;
  margin-bottom: 10px;
}
.term {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--lot-muted);
  margin-top: 8px;
}
.term-calc b {
  color: var(--lot-ink);
}
.term-bar {
  margin-top: 4px;
}
.facts {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--lot-muted);
}
.facts b {
  color: var(--lot-ink);
}
.section-note {
  font-size: 13px;
  color: var(--lot-faint);
  margin-top: 6px;
}
.flag {
  display: flex;
  gap: 8px;
  padding: 8px 0;
}
.flag-body {
  min-width: 0;
}
.flag-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lot-ink);
}
.flag-weight {
  color: var(--lot-faint);
  font-weight: 400;
  margin-left: 4px;
}
.flag-detail {
  font-size: 12px;
  color: var(--lot-muted);
}
.flag-source {
  font-size: 11px;
  color: var(--lot-faint);
  margin-top: 2px;
}
.prov-line {
  font-size: 12px;
  color: var(--lot-muted);
}
.prov-note {
  font-size: 11px;
  color: var(--lot-faint);
  margin-top: 8px;
}
</style>
