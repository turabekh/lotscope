<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { formatCurrency } from '@/lib/format'
import type { SpatialParcelResult } from '@/lib/types'
import { type AreaShape, useAreaSearchStore } from '@/stores/areaSearch'

const emit = defineEmits<{ select: [parcelNumber: string] }>()

const store = useAreaSearchStore()
const { active, shape, center, polygon, radiusM, loading, results, count, truncated } =
  storeToRefs(store)

const SHAPE_OPTIONS: { label: string; value: AreaShape; icon: string }[] = [
  { label: 'Radius', value: 'radius', icon: 'radio_button_unchecked' },
  { label: 'Polygon', value: 'polygon', icon: 'pentagon' },
]

const hasQuery = computed(() =>
  shape.value === 'radius' ? center.value !== null : polygon.value !== null,
)

function onRadius(value: number | null): void {
  if (typeof value === 'number') void store.setRadius(value)
}

function pick(result: SpatialParcelResult): void {
  emit('select', result.parcel_number)
}

function radiusLabel(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`
}

function distanceLabel(meters: number | null): string {
  if (meters === null) return ''
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`
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

        <div v-if="!hasQuery" class="area-hint">
          <q-icon :name="shape === 'radius' ? 'touch_app' : 'gesture'" size="16px" class="q-mr-xs" />
          <span v-if="shape === 'radius'">Tap the map to set a center point.</span>
          <span v-else>Click to add points; click the first point to close the shape.</span>
        </div>

        <template v-else>
          <div class="area-count">
            <q-spinner v-if="loading" size="16px" color="primary" class="q-mr-xs" />
            <q-icon v-else name="place" size="16px" class="q-mr-xs text-primary" />
            <span>
              <b>{{ count }}</b> lot<span v-if="count !== 1">s</span>
              <span v-if="shape === 'radius'"> within {{ radiusLabel(radiusM) }}</span>
              <span v-else> in this area</span>
              <span v-if="truncated" class="text-grey-6"> (first {{ count }})</span>
            </span>
          </div>

          <q-list dense class="area-list lot-scroll">
            <q-item
              v-for="result in results"
              :key="result.parcel_number"
              clickable
              @click="pick(result)"
            >
              <q-item-section>
                <q-item-label class="ellipsis">
                  {{ result.address ?? result.parcel_number }}
                </q-item-label>
                <q-item-label caption>
                  {{ result.base_zoning_code ?? '—' }}
                  <span v-if="result.is_vacant" class="text-amber-9">· Vacant</span>
                  <span v-if="result.market_value"> · {{ formatCurrency(result.market_value) }}</span>
                  <span v-if="result.distance_m !== null" class="text-grey-6">
                    · {{ distanceLabel(result.distance_m) }}</span
                  >
                </q-item-label>
              </q-item-section>
              <q-item-section v-if="result.opportunity_score !== null" side>
                <q-badge color="primary" outline>{{ result.opportunity_score }}</q-badge>
              </q-item-section>
            </q-item>
            <q-item v-if="!loading && results.length === 0">
              <q-item-section class="text-grey-6">
                No lots here. Try a {{ shape === 'radius' ? 'larger radius' : 'bigger area' }}.
              </q-item-section>
            </q-item>
          </q-list>
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
