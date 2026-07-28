<script setup lang="ts">
import { computed, ref } from 'vue'

import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { BuyBox, BuyBoxMatches, UnderwritingProfile } from '@/lib/types'
import { useMarketStore } from '@/stores/market'

const market = useMarketStore()

const RISK_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

const maxPrice = ref<number | null>(null)
const minMarginPct = ref<number | null>(null)
const minUnits = ref<number | null>(null)
const riskTolerance = ref<string | null>(null)

const saving = ref(false)
const result = ref<BuyBoxMatches | null>(null)
const errorMessage = ref<string | null>(null)

const hasAnyCriterion = computed(
  () =>
    maxPrice.value !== null ||
    minMarginPct.value !== null ||
    minUnits.value !== null ||
    riskTolerance.value !== null,
)

function buildBuyBox(): BuyBox {
  return {
    max_acquisition_price: maxPrice.value,
    min_margin: minMarginPct.value === null ? null : minMarginPct.value / 100,
    min_units: minUnits.value,
    risk_tolerance: riskTolerance.value,
  }
}

async function saveDefaultProfile(buyBox: BuyBox): Promise<void> {
  const profiles: UnderwritingProfile[] = await api.listUnderwritingProfiles()
  const existing = profiles.find((profile) => profile.is_default) ?? profiles[0]
  const payload = {
    name: existing?.name ?? 'My buy box',
    is_default: true,
    assumptions: existing?.assumptions ?? {},
    buy_box: buyBox,
  }
  if (existing) {
    await api.updateUnderwritingProfile(existing.id, payload)
    return
  }
  await api.createUnderwritingProfile(payload)
}

async function submit(): Promise<void> {
  saving.value = true
  errorMessage.value = null
  try {
    await saveDefaultProfile(buildBuyBox())
    result.value = await api.getBuyBoxMatches(market.active, 5)
  } catch {
    errorMessage.value = 'Your buy box could not be saved. Nothing was changed.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <q-card flat bordered class="rounded-borders" data-test="buy-box-onboarding">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="filter_alt" size="18px" class="q-mr-xs" />Set your buy box
      </div>
      <p class="lead">
        Tell us what you buy and we will show matching lots straight away. Every field is optional —
        a lot only matches a rule you actually set.
      </p>

      <div class="grid">
        <q-input
          v-model.number="maxPrice"
          type="number"
          dense
          outlined
          label="Most you would pay"
          prefix="$"
          data-test="buy-box-price"
        />
        <q-input
          v-model.number="minMarginPct"
          type="number"
          dense
          outlined
          label="Target margin"
          suffix="%"
          data-test="buy-box-margin"
        />
        <q-input
          v-model.number="minUnits"
          type="number"
          dense
          outlined
          label="Minimum units"
          data-test="buy-box-units"
        />
        <q-select
          v-model="riskTolerance"
          :options="RISK_OPTIONS"
          emit-value
          map-options
          dense
          outlined
          clearable
          label="Risk tolerance"
          data-test="buy-box-risk"
        />
      </div>

      <q-btn
        :loading="saving"
        :disable="!hasAnyCriterion"
        unelevated
        color="primary"
        class="q-mt-sm"
        label="Save and show matches"
        data-test="buy-box-submit"
        @click="submit"
      />

      <div v-if="errorMessage" class="note error" data-test="buy-box-error">{{ errorMessage }}</div>

      <div v-if="result" class="results" data-test="buy-box-results">
        <div class="results-head">
          <strong>{{ result.total }}</strong>
          matching {{ result.total === 1 ? 'lot' : 'lots' }} in
          {{ market.activeInfo?.name ?? result.market }}
        </div>

        <div v-if="result.total === 0" class="note">
          Nothing matches yet. Widening your price ceiling or margin target is usually the fastest
          change. Lots whose offer or margin could not be calculated are never counted as matches.
        </div>

        <router-link
          v-for="item in result.matches"
          :key="item.parcel_number"
          :to="{
            name: 'parcel',
            params: { market: market.active, id: item.parcel_number },
          }"
          class="match"
        >
          <span class="match-address">{{ item.address ?? item.parcel_number }}</span>
          <span class="match-figures lot-numeric">
            {{ item.max_allowable_offer === null ? '—' : formatCurrency(item.max_allowable_offer) }}
            <span v-if="item.est_margin !== null" class="match-margin">
              · {{ (item.est_margin * 100).toFixed(0) }}%
            </span>
          </span>
        </router-link>
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
  margin-bottom: 8px;
}
.lead {
  font-size: 12.5px;
  color: var(--lot-muted);
  line-height: 1.45;
  margin: 0 0 10px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}
.note {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--lot-muted);
  line-height: 1.45;
}
.note.error {
  color: var(--lot-negative, #c10015);
}
.results {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--lot-hairline, rgba(0, 0, 0, 0.08));
}
.results-head {
  font-size: 13px;
  color: var(--lot-ink);
  margin-bottom: 6px;
}
.match {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 8px;
  border-radius: var(--lot-radius-sm);
  text-decoration: none;
  color: var(--lot-ink);
  font-size: 12.5px;
}
.match:hover {
  background: var(--lot-surface-2, rgba(0, 0, 0, 0.04));
}
.match-address {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.match-figures {
  flex: none;
  font-weight: 600;
}
.match-margin {
  font-weight: 500;
  color: var(--lot-muted);
}
</style>
