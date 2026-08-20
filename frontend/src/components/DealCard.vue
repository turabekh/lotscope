<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'

import GenerateOfferDialog from '@/components/GenerateOfferDialog.vue'
import SensitivityHeatmap from '@/components/SensitivityHeatmap.vue'
import { useParcelStore } from '@/stores/parcel'

const offerOpen = ref(false)

const store = useParcelStore()
const { detail, deal, dealLoading, underwriting } = storeToRefs(store)

const acquisitionPrice = ref<number | null>(null)
const targetMarginPct = ref<number | null>(null)
const constructionCostPerSqft = ref<number | null>(null)

const MARGIN_MIN = 0
const MARGIN_MAX = 99
const COST_MIN = 1
const COST_MAX = 2000

const ORIGIN_LABEL: Record<string, string> = {
  platform_default: 'Platform default',
  market_default: 'Market default',
  derived: 'Derived from this parcel',
  user_override: 'Your profile',
  scenario_override: 'This scenario',
  authoritative_source: 'Source-reported',
}

const cases = computed(() => underwriting.value?.cases ?? [])
const assumptions = computed(() => underwriting.value?.assumptions ?? [])
const unavailable = computed(() => assumptions.value.filter((a) => a.value === null))
const grid = computed(() => underwriting.value?.sensitivity ?? null)

const scoreColor = computed(() => {
  const score = deal.value?.deal_score
  if (score == null) return 'blue-grey-6'
  if (score >= 60) return 'positive'
  if (score >= 35) return 'warning'
  return 'negative'
})

function money(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value < 0 ? '-' : ''
  return `${sign}$${Math.abs(Math.round(value)).toLocaleString('en-US')}`
}

function percent(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function originLabel(origin: string): string {
  return ORIGIN_LABEL[origin] ?? origin
}

const targetMarginText = computed(() => {
  const target = deal.value?.assumptions?.target_margin
  return target == null ? null : `${Math.round(target * 100)}%`
})

const heroSentence = computed(() => {
  const value = deal.value
  if (!value || value.infeasible || value.max_allowable_offer == null) return null
  return { offer: money(value.max_allowable_offer), margin: targetMarginText.value }
})

const provenance = computed(() => {
  const parts: string[] = []
  const comps = deal.value?.comp_count
  if (comps != null) parts.push(`ARV from ${comps} improved-sale comp${comps === 1 ? '' : 's'}`)
  const origins = new Set(assumptions.value.map((a) => a.origin))
  if (origins.has('scenario_override')) parts.push('costs you set for this scenario')
  else if (origins.has('user_override')) parts.push('your profile costs')
  else if (origins.has('market_default')) parts.push('market default costs')
  else parts.push('platform default costs')
  if (targetMarginText.value) parts.push(`${targetMarginText.value} target margin`)
  return parts.join(' · ')
})

function clamp(value: number | null, low: number, high: number): number | null {
  if (value == null) return null
  return Math.min(high, Math.max(low, value))
}

async function recompute(): Promise<void> {
  if (detail.value === null) return
  const margin = clamp(targetMarginPct.value, MARGIN_MIN, MARGIN_MAX)
  const cost = clamp(constructionCostPerSqft.value, COST_MIN, COST_MAX)
  targetMarginPct.value = margin
  constructionCostPerSqft.value = cost
  await store.loadDeal(detail.value.parcel_number, {
    acquisitionPrice: acquisitionPrice.value,
    targetMargin: margin != null ? margin / 100 : null,
    constructionCostPerSqft: cost,
  })
}

function reset(): void {
  if (detail.value === null) return
  acquisitionPrice.value = null
  targetMarginPct.value = null
  constructionCostPerSqft.value = null
  void store.loadDeal(detail.value.parcel_number)
}
</script>

<template>
  <q-card flat bordered class="rounded-borders" data-test="deal-card">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="payments" size="18px" class="q-mr-xs" />Deal analysis
        <q-space />
        <q-chip
          v-if="deal && deal.deal_score != null"
          dense
          square
          :color="scoreColor"
          text-color="white"
          icon="insights"
        >
          {{ deal.deal_score }}/100
          <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
            0-100, from the modelled margin against the target margin. Buying exactly at the max
            allowable offer scores 50 — the target is met, with no cushion. Higher means more margin
            than the target requires.
          </q-tooltip>
        </q-chip>
      </div>

      <div v-if="dealLoading && !deal" class="skeleton-block" data-test="deal-skeleton">
        <q-skeleton type="text" width="70%" height="28px" />
        <q-skeleton type="text" width="45%" class="q-mt-xs" />
        <div class="case-grid q-mt-sm">
          <q-skeleton v-for="n in 3" :key="n" type="rect" height="62px" />
        </div>
      </div>

      <template v-else-if="deal && deal.arv != null">
        <div v-if="deal.infeasible" class="infeasible-banner" data-test="deal-infeasible">
          <q-icon name="report_problem" size="16px" class="q-mr-xs" />
          Modelled build cost exceeds the finished value, so new construction is not economical here
          at any land price — the figures below describe that shortfall, not an opportunity.
        </div>
        <div v-else-if="deal.is_underpriced" class="underpriced-banner">
          <q-icon name="trending_down" size="16px" class="q-mr-xs" />
          Acquisition at or below max allowable offer — looks underpriced.
        </div>

        <div class="hero" data-test="deal-hero">
          <template v-if="heroSentence">
            Offer up to
            <span class="hero-figure lot-numeric" data-test="deal-mao">{{
              heroSentence.offer
            }}</span>
            <template v-if="heroSentence.margin">
              to clear a {{ heroSentence.margin }} margin
            </template>
          </template>
          <template v-else>
            <span class="hero-figure" data-test="deal-mao">No viable price</span>
            clears the target margin on this lot
          </template>
        </div>
        <div class="hero-note">
          Informational only — not an appraisal, and not legal or financial advice.
        </div>
        <div class="provenance" data-test="deal-provenance">{{ provenance }}</div>

        <div v-if="cases.length" class="case-grid q-mt-sm" data-test="case-strip">
          <div v-for="item in cases" :key="item.case" class="case" :class="item.case">
            <div class="case-label">{{ item.label }}</div>
            <div class="case-mao lot-numeric" :data-test="`case-mao-${item.case}`">
              {{ item.infeasible ? 'No viable price' : money(item.max_allowable_offer) }}
            </div>
            <div class="case-margin">
              {{ item.infeasible ? 'Build cost exceeds value' : `Margin ${percent(item.margin)}` }}
            </div>
            <q-tooltip max-width="240px" anchor="top middle" self="bottom middle">
              {{ item.rationale }}
            </q-tooltip>
          </div>
        </div>

        <SensitivityHeatmap v-if="grid" :grid="grid" class="q-mt-sm heat-embed" />

        <q-list dense class="breakdown q-mt-sm">
          <div class="breakdown-row">
            <span>Acquisition{{ deal.units ? ` · ${deal.units} unit(s)` : '' }}</span>
            <span class="lot-numeric">{{ money(deal.acquisition_cost) }}</span>
          </div>
          <div class="breakdown-row">
            <span>Construction</span
            ><span class="lot-numeric" data-test="breakdown-construction">{{
              money(deal.construction_cost)
            }}</span>
          </div>
          <div class="breakdown-row">
            <span>ARV (finished)</span><span class="lot-numeric">{{ money(deal.arv) }}</span>
          </div>
          <div class="breakdown-row">
            <span>Margin</span><span class="lot-numeric">{{ percent(deal.margin) }}</span>
          </div>
          <div class="breakdown-row">
            <span>ROI</span>
            <span class="lot-numeric">{{ percent(deal.roi) }}</span>
            <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
              Profit divided by acquisition, construction and soft costs. Selling costs are
              subtracted from profit but excluded from the basis.
            </q-tooltip>
          </div>
        </q-list>

        <div class="controls q-mt-sm" data-test="deal-controls">
          <div class="controls-title">Model a scenario</div>
          <div class="control-row">
            <q-input
              v-model.number="acquisitionPrice"
              dense
              outlined
              type="number"
              :min="0"
              label="Acquisition price ($)"
              :placeholder="String(Math.round(deal.acquisition_cost ?? 0))"
            />
            <q-input
              v-model.number="targetMarginPct"
              dense
              outlined
              type="number"
              :min="MARGIN_MIN"
              :max="MARGIN_MAX"
              label="Target margin (%)"
              :placeholder="String(Math.round((deal.assumptions?.target_margin ?? 0) * 100))"
            />
            <q-input
              v-model.number="constructionCostPerSqft"
              dense
              outlined
              type="number"
              :min="COST_MIN"
              :max="COST_MAX"
              label="Construction ($/sqft)"
              :placeholder="String(Math.round(deal.assumptions?.construction_cost_per_sqft ?? 0))"
            />
          </div>
          <div class="row q-gutter-sm q-mt-xs">
            <q-btn
              unelevated
              no-caps
              color="primary"
              icon="calculate"
              label="Recompute"
              :loading="dealLoading"
              @click="recompute"
            />
            <q-btn flat no-caps color="grey-7" label="Reset" @click="reset" />
            <q-space />
            <q-btn
              unelevated
              no-caps
              color="secondary"
              icon="description"
              label="Generate offer (PDF)"
              data-test="deal-generate-offer"
              @click="offerOpen = true"
            />
          </div>
          <div class="text-caption lot-text-muted q-mt-sm">
            Assumptions:
            {{
              deal.assumptions_source === 'calibrated'
                ? 'calibrated for this market'
                : 'market default'
            }}
          </div>
        </div>

        <div v-if="unavailable.length" class="excluded" data-test="unavailable-inputs">
          <q-icon name="info" size="14px" class="q-mr-xs" />
          {{ unavailable.length }} input{{ unavailable.length > 1 ? 's are' : ' is' }} unavailable,
          so these figures exclude
          {{ unavailable.map((a) => a.name.replace(/_/g, ' ')).join(', ') }}.
        </div>

        <q-expansion-item
          dense
          label="How this was computed"
          icon="notes"
          class="reasons"
          data-test="deal-disclosure"
        >
          <ul class="reason-list">
            <li v-for="(reason, index) in deal.reasons" :key="index">{{ reason }}</li>
          </ul>

          <template v-if="underwriting">
            <div class="formula lot-numeric">{{ underwriting.mao.formula }}</div>

            <div class="assumption-list">
              <div v-for="item in assumptions" :key="item.name" class="assumption">
                <span class="assumption-name">{{ item.name.replace(/_/g, ' ') }}</span>
                <span class="assumption-value lot-numeric">
                  {{ item.value === null ? 'Unavailable' : item.value }}
                </span>
                <span class="assumption-origin">{{ originLabel(item.origin) }}</span>
                <q-tooltip v-if="item.limitations" max-width="260px">
                  {{ item.limitations }}
                </q-tooltip>
              </div>
            </div>

            <div class="excluded">
              <strong>Not accounted for:</strong> {{ underwriting.mao.exclusions.join('; ') }}.
            </div>
          </template>
        </q-expansion-item>

        <GenerateOfferDialog
          v-model="offerOpen"
          :parcel-number="deal.parcel_number"
          :max-allowable-offer="deal.infeasible ? null : (deal.max_allowable_offer ?? null)"
        />
      </template>

      <div v-else-if="!dealLoading" class="text-body2 lot-text-muted q-mt-xs">
        {{
          deal?.reasons?.[0] ?? 'Not enough zoning or comparable-sales data to model a deal here.'
        }}
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
.hero {
  font-size: 17px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--lot-ink);
  margin-top: 4px;
}
.hero-figure {
  font-size: 22px;
  font-weight: 800;
}
.hero-note {
  font-size: 11.5px;
  color: var(--lot-muted);
  margin-top: 2px;
}
.provenance {
  font-size: 12px;
  color: var(--lot-muted);
  margin-top: 4px;
}
.skeleton-block {
  padding: 4px 0;
}
.case-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.case {
  padding: 8px;
  border-radius: var(--lot-radius-sm);
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.03));
  text-align: center;
}
.case.base {
  outline: 2px solid var(--lot-accent, #1976d2);
}
.case-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
}
.case-mao {
  font-size: 15px;
  font-weight: 700;
  color: var(--lot-ink);
}
.case-margin {
  font-size: 11.5px;
  color: var(--lot-muted);
}
.heat-embed :deep(.q-card) {
  box-shadow: none;
  border: none;
}
.breakdown-row {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  padding: 2px 0;
  color: var(--lot-ink);
}
.controls {
  border-top: 1px solid var(--lot-border, rgba(0, 0, 0, 0.08));
  padding-top: 8px;
}
.controls-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 6px;
}
.control-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
@media (max-width: 599px) {
  .control-row {
    grid-template-columns: 1fr;
  }
}
.infeasible-banner,
.underpriced-banner {
  display: flex;
  align-items: center;
  font-size: 12.5px;
  font-weight: 600;
  padding: 6px 8px;
  border-radius: var(--lot-radius-sm);
  margin-bottom: 6px;
}
.infeasible-banner {
  background: rgba(235, 87, 87, 0.12);
  color: #a03030;
}
.underpriced-banner {
  background: rgba(33, 150, 83, 0.12);
  color: #1c7a45;
}
.excluded {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--lot-muted);
  line-height: 1.4;
}
.reason-list {
  margin: 4px 0 0;
  padding-left: 18px;
  font-size: 12.5px;
  color: var(--lot-ink);
}
.formula {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--lot-muted);
  word-break: break-word;
}
.assumption-list {
  margin-top: 6px;
}
.assumption {
  display: grid;
  grid-template-columns: 1.4fr 0.7fr 1fr;
  gap: 6px;
  font-size: 11.5px;
  padding: 2px 0;
}
.assumption-name {
  color: var(--lot-ink);
}
.assumption-value {
  text-align: right;
}
.assumption-origin {
  color: var(--lot-muted);
  text-align: right;
}
</style>
