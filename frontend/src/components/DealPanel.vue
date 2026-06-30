<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { detail, deal, dealLoading } = storeToRefs(store)

const acquisitionPrice = ref<number | null>(null)
const targetMarginPct = ref<number | null>(null)

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

async function recompute(): Promise<void> {
  if (detail.value === null) return
  await store.loadDeal(detail.value.parcel_number, {
    acquisitionPrice: acquisitionPrice.value,
    targetMargin: targetMarginPct.value != null ? targetMarginPct.value / 100 : null,
  })
}

function reset(): void {
  if (detail.value === null) return
  acquisitionPrice.value = null
  targetMarginPct.value = null
  void store.loadDeal(detail.value.parcel_number)
}
</script>

<template>
  <q-card flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="calculate" size="18px" class="q-mr-xs" />Deal analysis
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="280px" anchor="bottom middle" self="top middle">
          A feasibility model: finished value (ARV) from nearby improved sales, minus construction,
          soft, and selling costs and the acquisition price, against a target margin. Informational
          — verify costs and comps before acting.
        </q-tooltip>
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
        </q-chip>
      </div>

      <q-inner-loading :showing="dealLoading" color="primary" />

      <template v-if="deal && deal.arv != null">
        <div v-if="deal.is_underpriced" class="underpriced-banner">
          <q-icon name="trending_down" size="16px" class="q-mr-xs" />
          Acquisition at or below max allowable offer — looks underpriced.
        </div>

        <div class="metric-grid q-mt-sm">
          <div class="metric metric--hero">
            <div class="metric-label">Max allowable offer</div>
            <div class="metric-value">{{ money(deal.max_allowable_offer) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">ARV (finished)</div>
            <div class="metric-value">{{ money(deal.arv) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Profit</div>
            <div class="metric-value" :class="(deal.profit ?? 0) < 0 ? 'text-negative' : 'text-positive'">
              {{ money(deal.profit) }}
            </div>
          </div>
          <div class="metric">
            <div class="metric-label">Margin</div>
            <div class="metric-value">{{ percent(deal.margin) }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">ROI</div>
            <div class="metric-value">{{ percent(deal.roi) }}</div>
          </div>
        </div>

        <q-list dense class="breakdown q-mt-sm">
          <div class="breakdown-row">
            <span>Acquisition{{ deal.units ? ` · ${deal.units} unit(s)` : '' }}</span>
            <span>{{ money(deal.acquisition_cost) }}</span>
          </div>
          <div class="breakdown-row">
            <span>Construction</span><span>{{ money(deal.construction_cost) }}</span>
          </div>
          <div class="breakdown-row">
            <span>Soft costs</span><span>{{ money(deal.soft_cost) }}</span>
          </div>
          <div class="breakdown-row">
            <span>Selling costs</span><span>{{ money(deal.selling_cost) }}</span>
          </div>
          <div class="breakdown-row breakdown-row--total">
            <span>All-in cost</span><span>{{ money(deal.total_cost) }}</span>
          </div>
        </q-list>

        <div class="row items-center q-gutter-xs q-mt-sm">
          <q-chip dense square outline color="grey-7" :icon="'verified'">
            {{ deal.confidence }} confidence · {{ deal.comp_count }} comp(s)
          </q-chip>
        </div>

        <q-expansion-item dense label="Model a scenario" icon="tune" class="q-mt-xs scenario">
          <div class="q-pa-sm q-gutter-sm">
            <q-input
              v-model.number="acquisitionPrice"
              dense
              outlined
              type="number"
              label="Acquisition price ($)"
              :placeholder="String(Math.round(deal.acquisition_cost ?? 0))"
            />
            <q-input
              v-model.number="targetMarginPct"
              dense
              outlined
              type="number"
              label="Target margin (%)"
              :placeholder="String(Math.round(deal.assumptions.target_margin * 100))"
            />
            <div class="row q-gutter-sm">
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
            </div>
          </div>
        </q-expansion-item>

        <q-expansion-item dense label="How this was computed" icon="notes" class="reasons">
          <ul class="reason-list">
            <li v-for="(reason, index) in deal.reasons" :key="index">{{ reason }}</li>
          </ul>
        </q-expansion-item>
      </template>

      <div v-else-if="!dealLoading" class="text-body2 text-grey-6 q-mt-xs">
        {{ deal?.reasons?.[0] ?? 'Not enough zoning or comparable-sales data to model a deal here.' }}
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
.underpriced-banner {
  display: flex;
  align-items: center;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--lot-score-positive);
  background: var(--lot-positive-soft);
  border-radius: var(--lot-radius-sm);
  padding: 6px 10px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.metric {
  background: var(--lot-surface-2);
  border-radius: var(--lot-radius-sm);
  padding: 8px 10px;
}
.metric--hero {
  grid-column: 1 / -1;
  background: var(--lot-accent-soft);
}
.metric-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--lot-muted);
}
.metric-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--lot-ink);
}
.metric--hero .metric-value {
  font-size: 20px;
  color: var(--lot-accent);
}
.breakdown {
  border-top: 1px solid var(--lot-surface-2);
  padding-top: 6px;
}
.breakdown-row {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  color: var(--lot-ink);
  padding: 3px 2px;
}
.breakdown-row--total {
  font-weight: 700;
  border-top: 1px dashed var(--lot-border);
  margin-top: 2px;
  padding-top: 6px;
}
.reason-list {
  margin: 0;
  padding: 4px 0 4px 18px;
}
.reason-list li {
  font-size: 12px;
  color: var(--lot-muted);
  margin-bottom: 3px;
}
</style>
