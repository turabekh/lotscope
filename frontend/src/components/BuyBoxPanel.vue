<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAreaSearchStore } from '@/stores/areaSearch'
import { USE_CLASS_OPTIONS, useFiltersStore } from '@/stores/filters'
import { useMarketStore } from '@/stores/market'

const filters = useFiltersStore()
const { vacantOnly, useClasses } = storeToRefs(filters)
const areaSearch = useAreaSearchStore()
const {
  minValue,
  maxValue,
  minLotArea,
  maxLotArea,
  minScore,
  minDistress,
  delinquentOnly,
  sheriffSaleOnly,
  underpricedOnly,
  byRightOnly,
} = storeToRefs(areaSearch)
const market = useMarketStore()
const router = useRouter()

const VALUE_MAX = 1_000_000
const AREA_MAX = 15_000

function money(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(v % 1_000_000 === 0 ? 0 : 1)}M`
  if (v >= 1000) return `$${Math.round(v / 1000)}k`
  return `$${v}`
}

const valueRange = computed<{ min: number; max: number }>({
  get: () => ({ min: minValue.value ?? 0, max: maxValue.value ?? VALUE_MAX }),
  set: (r) => {
    minValue.value = r.min <= 0 ? null : r.min
    maxValue.value = r.max >= VALUE_MAX ? null : r.max
  },
})
const areaRange = computed<{ min: number; max: number }>({
  get: () => ({ min: minLotArea.value ?? 0, max: maxLotArea.value ?? AREA_MAX }),
  set: (r) => {
    minLotArea.value = r.min <= 0 ? null : r.min
    maxLotArea.value = r.max >= AREA_MAX ? null : r.max
  },
})
const valueLabel = computed(() =>
  minValue.value === null && maxValue.value === null
    ? 'Any'
    : `${money(minValue.value ?? 0)} – ${maxValue.value === null ? `${money(VALUE_MAX)}+` : money(maxValue.value)}`,
)
const areaLabel = computed(() =>
  minLotArea.value === null && maxLotArea.value === null
    ? 'Any'
    : `${(minLotArea.value ?? 0).toLocaleString()} – ${maxLotArea.value === null ? `${AREA_MAX.toLocaleString()}+` : maxLotArea.value.toLocaleString()} sq ft`,
)

function onSlider(target: 'score' | 'distress', value: number): void {
  const clean = value > 0 ? value : null
  if (target === 'score') minScore.value = clean
  else minDistress.value = clean
}

const activeCount = computed(() => {
  let n = 0
  if (vacantOnly.value) n += 1
  if (useClasses.value.length > 0) n += 1
  if (minValue.value !== null || maxValue.value !== null) n += 1
  if (minLotArea.value !== null || maxLotArea.value !== null) n += 1
  if (minScore.value !== null) n += 1
  if (minDistress.value !== null) n += 1
  if (delinquentOnly.value) n += 1
  if (sheriffSaleOnly.value) n += 1
  if (underpricedOnly.value) n += 1
  if (byRightOnly.value) n += 1
  return n
})

function reset(): void {
  vacantOnly.value = false
  useClasses.value = []
  minValue.value = null
  maxValue.value = null
  minLotArea.value = null
  maxLotArea.value = null
  minScore.value = null
  minDistress.value = null
  delinquentOnly.value = false
  sheriffSaleOnly.value = false
  underpricedOnly.value = false
  byRightOnly.value = false
}

function saveAlert(): void {
  void router.push({
    name: 'saved-searches',
    params: { market: market.active },
    query: vacantOnly.value ? { vacant: '1' } : {},
  })
}
</script>

<template>
  <div class="buy-box">
    <div class="bb-section">
      <div class="bb-label">Signals</div>
      <div class="bb-chips">
        <q-chip
          clickable
          dense
          :color="vacantOnly ? 'amber-8' : 'grey-2'"
          :text-color="vacantOnly ? 'white' : 'grey-9'"
          icon="grass"
          @click="vacantOnly = !vacantOnly"
        >
          Vacant
        </q-chip>
        <q-chip
          clickable
          dense
          :color="delinquentOnly ? 'primary' : 'grey-2'"
          :text-color="delinquentOnly ? 'white' : 'grey-9'"
          icon="receipt_long"
          @click="delinquentOnly = !delinquentOnly"
        >
          Tax delinquent
        </q-chip>
        <q-chip
          clickable
          dense
          :color="sheriffSaleOnly ? 'primary' : 'grey-2'"
          :text-color="sheriffSaleOnly ? 'white' : 'grey-9'"
          icon="gavel"
          @click="sheriffSaleOnly = !sheriffSaleOnly"
        >
          Sheriff sale
        </q-chip>
        <q-chip
          clickable
          dense
          :color="underpricedOnly ? 'positive' : 'grey-2'"
          :text-color="underpricedOnly ? 'white' : 'grey-9'"
          icon="trending_down"
          @click="underpricedOnly = !underpricedOnly"
        >
          Underpriced
        </q-chip>
        <q-chip
          clickable
          dense
          :color="byRightOnly ? 'primary' : 'grey-2'"
          :text-color="byRightOnly ? 'white' : 'grey-9'"
          icon="check_circle"
          @click="byRightOnly = !byRightOnly"
        >
          By-right
        </q-chip>
      </div>
    </div>

    <div class="bb-section">
      <div class="bb-label">Zoning use class</div>
      <div class="bb-chips">
        <q-chip
          v-for="option in USE_CLASS_OPTIONS"
          :key="option.value"
          clickable
          dense
          :color="useClasses.includes(option.value) ? 'primary' : 'grey-2'"
          :text-color="useClasses.includes(option.value) ? 'white' : 'grey-9'"
          @click="filters.toggleClass(option.value)"
        >
          <span class="dot q-mr-xs" :style="{ background: option.color }" />
          {{ option.label }}
        </q-chip>
      </div>
    </div>

    <div class="bb-section">
      <div class="bb-slider-head">
        <span class="bb-label">Min opportunity score</span>
        <span class="bb-slider-val">{{ minScore ?? 'Any' }}</span>
      </div>
      <q-slider
        :model-value="minScore ?? 0"
        :min="0"
        :max="100"
        :step="5"
        color="primary"
        @update:model-value="(v) => onSlider('score', v ?? 0)"
      />
      <div class="bb-slider-head q-mt-sm">
        <span class="bb-label">Min distress score</span>
        <span class="bb-slider-val">{{ minDistress ?? 'Any' }}</span>
      </div>
      <q-slider
        :model-value="minDistress ?? 0"
        :min="0"
        :max="100"
        :step="5"
        color="deep-orange"
        @update:model-value="(v) => onSlider('distress', v ?? 0)"
      />
    </div>

    <div class="bb-section">
      <div class="bb-slider-head">
        <span class="bb-label">Market value</span>
        <span class="bb-slider-val">{{ valueLabel }}</span>
      </div>
      <q-range
        v-model="valueRange"
        :min="0"
        :max="VALUE_MAX"
        :step="25000"
        color="primary"
        class="bb-range"
      />
      <div class="bb-slider-head q-mt-md">
        <span class="bb-label">Lot area</span>
        <span class="bb-slider-val">{{ areaLabel }}</span>
      </div>
      <q-range
        v-model="areaRange"
        :min="0"
        :max="AREA_MAX"
        :step="500"
        color="primary"
        class="bb-range"
      />
    </div>

    <div class="bb-footer">
      <q-btn
        flat
        dense
        no-caps
        size="sm"
        color="primary"
        icon="notifications_active"
        label="Save as alert"
        @click="saveAlert"
      />
      <q-space />
      <q-btn
        flat
        dense
        no-caps
        size="sm"
        color="grey-7"
        icon="restart_alt"
        :label="activeCount > 0 ? `Reset (${activeCount})` : 'Reset'"
        :disable="activeCount === 0"
        @click="reset"
      />
    </div>
  </div>
</template>

<style scoped>
.buy-box {
  width: 100%;
}
.bb-section {
  padding: 12px 2px;
  border-bottom: 1px solid var(--lot-border);
}
.bb-section:last-of-type {
  border-bottom: none;
}
.bb-label {
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.bb-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.bb-slider-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 2px;
}
.bb-slider-head .bb-label {
  margin-bottom: 0;
}
.bb-slider-val {
  font-size: 13px;
  font-weight: 700;
  color: var(--lot-ink);
}
.bb-range {
  padding: 0 6px;
}
.bb-footer {
  display: flex;
  align-items: center;
  padding: 8px 0 2px;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
}
</style>
