<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { ref, watch } from 'vue'

import { type AreaShape, useAreaSearchStore } from '@/stores/areaSearch'
import { BASEMAP_OPTIONS, COLOR_MODE_OPTIONS, useFiltersStore } from '@/stores/filters'

const props = defineProps<{ embedded?: boolean }>()

const filters = useFiltersStore()
const { colorMode, show3d, basemap } = storeToRefs(filters)
const areaSearch = useAreaSearchStore()
const { active, shape, radiusM, neighborhood, neighborhoods } = storeToRefs(areaSearch)
const $q = useQuasar()

const open = ref(props.embedded ? true : !$q.screen.lt.sm)

const SHAPE_OPTIONS: { label: string; value: AreaShape; icon: string }[] = [
  { label: 'Radius', value: 'radius', icon: 'radio_button_unchecked' },
  { label: 'Polygon', value: 'polygon', icon: 'pentagon' },
  { label: 'Area', value: 'neighborhood', icon: 'map' },
]

const neighborhoodOptions = ref<string[]>([])

watch(
  [active, shape],
  () => {
    if (active.value && shape.value === 'neighborhood') void areaSearch.loadNeighborhoods()
  },
  { immediate: true },
)
watch(neighborhoods, (list) => (neighborhoodOptions.value = list), { immediate: true })

function onRadius(value: number | null): void {
  if (typeof value === 'number') void areaSearch.setRadius(value)
}
function onNeighborhood(value: string | null): void {
  if (value !== null) void areaSearch.searchNeighborhood(value)
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
  <q-card class="map-controls lot-scroll" :class="{ embedded }" flat>
    <div class="mc-header">
      <q-icon name="map" size="18px" class="text-primary q-mr-sm" />
      <span class="mc-title">Map</span>
      <q-space />
      <q-btn
        v-if="!embedded"
        flat
        dense
        round
        size="sm"
        color="grey-7"
        :icon="open ? 'expand_less' : 'expand_more'"
        :aria-label="open ? 'Collapse controls' : 'Expand controls'"
        @click="open = !open"
      />
    </div>

    <q-slide-transition>
      <div v-show="open" class="mc-body">
        <section class="mc-section">
          <div class="mc-label"><q-icon name="layers" size="14px" class="q-mr-xs" />Base map</div>
          <q-btn-toggle
            v-model="basemap"
            spread
            no-caps
            dense
            unelevated
            rounded
            toggle-color="primary"
            color="grey-2"
            text-color="grey-9"
            :options="BASEMAP_OPTIONS"
          />
        </section>

        <section class="mc-section">
          <div class="mc-label">
            <q-icon name="palette" size="14px" class="q-mr-xs" />Color lots by
          </div>
          <q-btn-toggle
            v-model="colorMode"
            spread
            no-caps
            dense
            unelevated
            rounded
            toggle-color="primary"
            color="grey-2"
            text-color="grey-9"
            :options="COLOR_MODE_OPTIONS"
          />
          <div class="mc-legend">
            <template v-if="colorMode === 'vacancy'">
              <span class="dot" style="background: var(--lot-sev-medium)" />Vacant
              <span class="dot q-ml-md" style="background: var(--lot-accent)" />Built
            </template>
            <template v-else>
              <span class="lg-end">{{ colorMode === 'opportunity' ? 'Low' : 'Low risk' }}</span>
              <span
                class="gradient"
                :style="{
                  background:
                    colorMode === 'opportunity'
                      ? 'linear-gradient(90deg,var(--lot-sev-high),var(--lot-sev-medium),var(--lot-score-positive),var(--lot-score-positive))'
                      : 'linear-gradient(90deg,var(--lot-score-positive),var(--lot-score-positive),var(--lot-sev-medium),var(--lot-sev-high))',
                }"
              />
              <span class="lg-end">{{ colorMode === 'opportunity' ? 'High' : 'High risk' }}</span>
            </template>
          </div>
        </section>

        <section class="mc-section">
          <q-toggle
            v-model="show3d"
            icon="deployed_code"
            label="3D building envelope"
            dense
            color="primary"
          />
        </section>

        <section class="mc-section">
          <q-btn
            :color="active ? 'primary' : 'grey-2'"
            :text-color="active ? 'white' : 'primary'"
            unelevated
            no-caps
            dense
            class="full-width"
            :icon="active ? 'close' : 'my_location'"
            :label="active ? 'Done drawing' : 'Search this area'"
            @click="areaSearch.toggle()"
          />
          <template v-if="active">
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
              class="q-mt-sm"
              :options="SHAPE_OPTIONS"
              @update:model-value="(value: AreaShape) => areaSearch.setShape(value)"
            />
            <div v-if="shape === 'radius'" class="mc-radius">
              <div class="mc-radius-label">
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
              <div class="mc-hint">Tap the map to set a center point.</div>
            </div>
            <q-select
              v-else-if="shape === 'neighborhood'"
              :model-value="neighborhood"
              :options="neighborhoodOptions"
              outlined
              dense
              clearable
              use-input
              input-debounce="0"
              label="Neighborhood"
              class="q-mt-sm"
              :loading="neighborhoods.length === 0"
              @update:model-value="onNeighborhood"
              @filter="filterNeighborhoods"
            />
            <div v-else class="mc-hint">Click the map to add points; click the first to close.</div>
          </template>
        </section>
      </div>
    </q-slide-transition>
  </q-card>
</template>

<style scoped>
.map-controls {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 5;
  width: 258px;
  max-width: calc(100% - 24px);
  max-height: calc(100% - 24px);
  overflow-y: auto;
  border-radius: var(--lot-radius);
  background: var(--lot-surface);
  border: 1px solid var(--lot-border);
  box-shadow: var(--lot-shadow-lg);
}
.map-controls.embedded {
  position: static;
  width: 100%;
  max-width: none;
  max-height: none;
  overflow: visible;
  border: none;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}
.map-controls.embedded .mc-header {
  position: static;
  padding: 4px 2px 10px;
  border-bottom: 1px solid var(--lot-border);
  background: transparent;
}
.map-controls.embedded .mc-section {
  padding: 12px 2px;
}
.mc-header {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  padding: 10px 8px 10px 14px;
  background: var(--lot-surface);
  border-bottom: 1px solid var(--lot-border);
}
.mc-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--lot-ink);
}
.mc-section {
  padding: 12px 14px;
  border-bottom: 1px solid var(--lot-border);
}
.mc-section:last-child {
  border-bottom: none;
}
.mc-label {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.mc-label .q-icon {
  color: var(--lot-faint);
}
.mc-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--lot-muted);
}
.mc-legend .lg-end {
  font-size: 11px;
  white-space: nowrap;
}
.mc-radius {
  margin-top: 8px;
}
.mc-radius-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--lot-muted);
}
.mc-hint {
  margin-top: 6px;
  font-size: 11.5px;
  line-height: 1.35;
  color: var(--lot-faint);
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
}
.gradient {
  flex: 1;
  height: 8px;
  border-radius: 5px;
}
</style>
