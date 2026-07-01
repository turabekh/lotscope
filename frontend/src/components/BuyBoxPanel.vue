<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'

import { useAreaSearchStore } from '@/stores/areaSearch'
import { USE_CLASS_OPTIONS, useFiltersStore } from '@/stores/filters'
import { useMarketStore } from '@/stores/market'

const filters = useFiltersStore()
const { vacantOnly, useClasses } = storeToRefs(filters)
const areaSearch = useAreaSearchStore()
const { minValue, maxValue, minLotArea, maxLotArea, minScore } = storeToRefs(areaSearch)
const market = useMarketStore()
const router = useRouter()

const numRefs = { minValue, maxValue, minLotArea, maxLotArea, minScore }

function onNum(field: keyof typeof numRefs, value: string | number | null): void {
  const parsed = value === null || value === '' ? null : Number(value)
  numRefs[field].value = parsed !== null && Number.isFinite(parsed) ? parsed : null
}

function reset(): void {
  vacantOnly.value = false
  useClasses.value = []
  minValue.value = null
  maxValue.value = null
  minLotArea.value = null
  maxLotArea.value = null
  minScore.value = null
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
      <q-toggle v-model="vacantOnly" label="Vacant lots only" dense color="amber-8" />
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
      <div class="bb-label">Buy box</div>
      <div class="bb-grid">
        <q-input
          :model-value="minValue"
          type="number"
          outlined
          dense
          label="Min $"
          @update:model-value="(value) => onNum('minValue', value)"
        />
        <q-input
          :model-value="maxValue"
          type="number"
          outlined
          dense
          label="Max $"
          @update:model-value="(value) => onNum('maxValue', value)"
        />
        <q-input
          :model-value="minLotArea"
          type="number"
          outlined
          dense
          label="Min sq ft"
          @update:model-value="(value) => onNum('minLotArea', value)"
        />
        <q-input
          :model-value="maxLotArea"
          type="number"
          outlined
          dense
          label="Max sq ft"
          @update:model-value="(value) => onNum('maxLotArea', value)"
        />
        <q-input
          :model-value="minScore"
          type="number"
          outlined
          dense
          label="Min score"
          class="bb-wide"
          @update:model-value="(value) => onNum('minScore', value)"
        />
      </div>
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
        label="Reset"
        @click="reset"
      />
    </div>
  </div>
</template>

<style scoped>
.buy-box {
  width: 320px;
  max-width: 92vw;
}
.bb-section {
  padding: 12px 14px;
  border-bottom: 1px solid var(--lot-border);
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
.bb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.bb-wide {
  grid-column: 1 / -1;
}
.bb-footer {
  display: flex;
  align-items: center;
  padding: 8px 12px;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
}
</style>
