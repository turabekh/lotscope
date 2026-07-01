<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'

import { type AreaShape, useAreaSearchStore } from '@/stores/areaSearch'

const store = useAreaSearchStore()
const {
  active,
  shape,
  center,
  polygon,
  neighborhood,
  neighborhoods,
  radiusM,
  minValue,
  maxValue,
  minLotArea,
  maxLotArea,
  minScore,
  loading,
  count,
  truncated,
} = storeToRefs(store)

type Criterion = 'minValue' | 'maxValue' | 'minLotArea' | 'maxLotArea' | 'minScore'
const criterionRefs = { minValue, maxValue, minLotArea, maxLotArea, minScore }
let rerunTimer: ReturnType<typeof setTimeout> | undefined

function setCriterion(field: Criterion, value: string | number | null): void {
  const n = value === null || value === '' ? null : Number(value)
  criterionRefs[field].value = n !== null && Number.isFinite(n) ? n : null
  clearTimeout(rerunTimer)
  rerunTimer = setTimeout(() => void store.rerun(), 400)
}

const SHAPE_OPTIONS: { label: string; value: AreaShape; icon: string }[] = [
  { label: 'Radius', value: 'radius', icon: 'radio_button_unchecked' },
  { label: 'Polygon', value: 'polygon', icon: 'pentagon' },
  { label: 'Area', value: 'neighborhood', icon: 'map' },
]

const hasQuery = computed(() => {
  if (shape.value === 'radius') return center.value !== null
  if (shape.value === 'polygon') return polygon.value !== null
  return neighborhood.value !== null
})

const neighborhoodOptions = ref<string[]>([])

watch(
  [active, shape],
  () => {
    if (active.value && shape.value === 'neighborhood') void store.loadNeighborhoods()
  },
  { immediate: true },
)

watch(neighborhoods, (list) => (neighborhoodOptions.value = list), { immediate: true })

function onRadius(value: number | null): void {
  if (typeof value === 'number') void store.setRadius(value)
}

function onNeighborhood(value: string | null): void {
  if (value !== null) void store.searchNeighborhood(value)
}

function filterNeighborhoods(value: string, update: (callback: () => void) => void): void {
  update(() => {
    const needle = value.toLowerCase()
    neighborhoodOptions.value = needle
      ? neighborhoods.value.filter((name) => name.toLowerCase().includes(needle))
      : neighborhoods.value
  })
}

function radiusLabel(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`
}
</script>

<template>
  <q-card class="area-panel" flat>
    <q-btn
      :color="active ? 'primary' : 'white'"
      :text-color="active ? 'white' : 'primary'"
      unelevated
      no-caps
      dense
      class="area-toggle"
      :icon="active ? 'close' : 'my_location'"
      :label="active ? 'Done' : 'Search this area'"
      @click="store.toggle()"
    />

    <q-slide-transition>
      <div v-show="active" class="area-body">
        <q-btn-toggle
          :model-value="shape"
          spread
          no-caps
          dense
          unelevated
          rounded
          toggle-color="primary"
          color="grey-2"
          text-color="grey-9"
          class="q-mb-sm"
          :options="SHAPE_OPTIONS"
          @update:model-value="(value: AreaShape) => store.setShape(value)"
        />

        <div v-if="shape === 'radius'" class="area-radius">
          <div class="area-label">
            <span>Radius</span>
            <span class="text-primary text-weight-bold">{{ radiusLabel(radiusM) }}</span>
          </div>
          <q-slider
            :model-value="radiusM"
            :min="100"
            :max="2000"
            :step="50"
            color="primary"
            @change="onRadius"
          />
        </div>

        <q-select
          v-if="shape === 'neighborhood'"
          :model-value="neighborhood"
          :options="neighborhoodOptions"
          outlined
          dense
          clearable
          use-input
          input-debounce="0"
          label="Neighborhood"
          class="q-mb-xs"
          :loading="neighborhoods.length === 0"
          @update:model-value="onNeighborhood"
          @filter="filterNeighborhoods"
        />

        <q-expansion-item dense label="Buy box" icon="tune" class="buy-box q-mb-xs">
          <div class="buy-box-grid">
            <q-input
              :model-value="minValue"
              type="number"
              outlined
              dense
              label="Min $"
              @update:model-value="(v) => setCriterion('minValue', v)"
            />
            <q-input
              :model-value="maxValue"
              type="number"
              outlined
              dense
              label="Max $"
              @update:model-value="(v) => setCriterion('maxValue', v)"
            />
            <q-input
              :model-value="minLotArea"
              type="number"
              outlined
              dense
              label="Min sq ft"
              @update:model-value="(v) => setCriterion('minLotArea', v)"
            />
            <q-input
              :model-value="maxLotArea"
              type="number"
              outlined
              dense
              label="Max sq ft"
              @update:model-value="(v) => setCriterion('maxLotArea', v)"
            />
            <q-input
              :model-value="minScore"
              type="number"
              outlined
              dense
              label="Min score"
              class="buy-box-wide"
              @update:model-value="(v) => setCriterion('minScore', v)"
            />
          </div>
        </q-expansion-item>

        <div v-if="!hasQuery" class="area-hint">
          <q-icon
            :name="shape === 'radius' ? 'touch_app' : shape === 'polygon' ? 'gesture' : 'map'"
            size="16px"
            class="q-mr-xs"
          />
          <span v-if="shape === 'radius'">Tap the map to set a center point.</span>
          <span v-else-if="shape === 'polygon'">
            Click to add points; click the first point to close the shape.
          </span>
          <span v-else>Pick a Philadelphia neighborhood.</span>
        </div>

        <template v-else>
          <div class="area-count">
            <q-spinner v-if="loading" size="16px" color="primary" class="q-mr-xs" />
            <q-icon v-else name="place" size="16px" class="q-mr-xs text-primary" />
            <span>
              <b>{{ count }}</b> lot<span v-if="count !== 1">s</span>
              <span v-if="shape === 'radius'"> within {{ radiusLabel(radiusM) }}</span>
              <span v-else-if="shape === 'neighborhood'"> in {{ neighborhood }}</span>
              <span v-else> in this area</span>
              <span v-if="truncated" class="text-grey-6"> (first {{ count }})</span>
            </span>
            <span class="area-hint-inline">· listed in the left pane</span>
          </div>
        </template>
      </div>
    </q-slide-transition>
  </q-card>
</template>

<style scoped>
.area-panel {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 5;
  width: 280px;
  max-width: calc(100vw - 24px);
  border-radius: var(--lot-radius);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: 0 8px 26px rgba(15, 23, 42, 0.2);
  overflow: hidden;
}
.area-toggle {
  width: 100%;
  border-radius: 0;
}
.area-body {
  padding: 10px 14px 12px;
}
.area-radius {
  padding-bottom: 4px;
}
.buy-box-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 6px 4px 2px;
}
.buy-box-wide {
  grid-column: 1 / -1;
}
.area-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--lot-muted);
  margin-bottom: 2px;
}
.area-hint {
  display: flex;
  align-items: center;
  font-size: 12.5px;
  color: var(--lot-faint);
  padding: 6px 0;
}
.area-count {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--lot-ink);
  padding: 4px 0 6px;
}
.area-list {
  max-height: 240px;
  overflow-y: auto;
}
</style>
