<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { ref } from 'vue'

import {
  BASEMAP_OPTIONS,
  COLOR_MODE_OPTIONS,
  USE_CLASS_OPTIONS,
  useFiltersStore,
} from '@/stores/filters'

const store = useFiltersStore()
const { vacantOnly, useClasses, colorMode, show3d, basemap, activeCount } = storeToRefs(store)
const $q = useQuasar()
const open = ref(!$q.screen.lt.sm)
</script>

<template>
  <q-card class="filter-panel lot-scroll" flat>
    <div class="fp-header">
      <q-icon name="tune" size="19px" class="text-primary q-mr-sm" />
      <span class="fp-title">Map controls</span>
      <q-badge v-if="activeCount" color="primary" rounded class="q-ml-xs">{{ activeCount }}</q-badge>
      <q-space />
      <q-btn
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
      <div v-show="open" class="fp-body">
        <section class="fp-section">
          <div class="fp-label"><q-icon name="layers" size="15px" class="q-mr-xs" />Base map</div>
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
            class="fp-toggle"
            :options="BASEMAP_OPTIONS"
          />
        </section>

        <section class="fp-section">
          <div class="fp-label"><q-icon name="palette" size="15px" class="q-mr-xs" />Color lots by</div>
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
            class="fp-toggle"
            :options="COLOR_MODE_OPTIONS"
          />

          <div class="fp-legend">
            <template v-if="colorMode === 'vacancy'">
              <span class="dot" style="background: #f9a825" />Vacant
              <span class="dot q-ml-md" style="background: #1565c0" />Built
            </template>
            <template v-else>
              <span class="lg-end">{{ colorMode === 'opportunity' ? 'Low' : 'Low risk' }}</span>
              <span
                class="gradient"
                :style="{
                  background:
                    colorMode === 'opportunity'
                      ? 'linear-gradient(90deg,#c62828,#f9a825,#9ccc65,#2e7d32)'
                      : 'linear-gradient(90deg,#2e7d32,#9ccc65,#f9a825,#c62828)',
                }"
              />
              <span class="lg-end">{{ colorMode === 'opportunity' ? 'High' : 'High risk' }}</span>
            </template>
          </div>
          <div class="fp-note">
            <q-icon name="place" size="14px" class="q-mr-xs" />
            <span>
              Pins mark vacant lots{{ colorMode === 'vacancy' ? '.' : `, shaded by ${colorMode}.` }}
              {{ colorMode === 'vacancy' ? '' : 'Scored vacant lots only.' }}
            </span>
          </div>
        </section>

        <section class="fp-section">
          <div class="fp-label"><q-icon name="visibility" size="15px" class="q-mr-xs" />Display</div>
          <q-toggle
            v-model="show3d"
            icon="deployed_code"
            label="3D building envelope"
            dense
            color="primary"
          />
          <div class="fp-note fp-note--indent">
            Extrudes the selected lot to its by-right height after setbacks. Approximate.
          </div>
          <q-toggle
            v-model="vacantOnly"
            label="Vacant lots only"
            dense
            color="amber-8"
            class="q-mt-sm"
          />
          <div class="fp-note fp-note--indent">Hide built parcels and show only likely-vacant lots.</div>
        </section>

        <section class="fp-section">
          <div class="fp-label">
            <q-icon name="category" size="15px" class="q-mr-xs" />Zoning use class
          </div>
          <div class="fp-chips">
            <q-chip
              v-for="option in USE_CLASS_OPTIONS"
              :key="option.value"
              clickable
              dense
              :color="useClasses.includes(option.value) ? 'primary' : 'grey-2'"
              :text-color="useClasses.includes(option.value) ? 'white' : 'grey-9'"
              @click="store.toggleClass(option.value)"
            >
              <span class="dot q-mr-xs" :style="{ background: option.color }" />
              {{ option.label }}
            </q-chip>
          </div>
        </section>

        <div class="fp-footer">
          <q-btn
            flat
            dense
            no-caps
            size="sm"
            color="grey-7"
            icon="restart_alt"
            label="Reset filters"
            @click="store.reset()"
          />
        </div>
      </div>
    </q-slide-transition>
  </q-card>
</template>

<style scoped>
.filter-panel {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 5;
  width: 258px;
  max-width: calc(100vw - 24px);
  max-height: calc(100% - 24px);
  overflow-y: auto;
  border-radius: var(--lot-radius);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: 0 8px 26px rgba(15, 23, 42, 0.2);
}
.fp-header {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  padding: 10px 8px 10px 14px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--lot-border);
}
.fp-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--lot-ink);
}
.fp-section {
  padding: 12px 14px;
  border-bottom: 1px solid var(--lot-border);
}
.fp-label {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--lot-muted);
  margin-bottom: 8px;
}
.fp-label .q-icon {
  color: var(--lot-faint);
}
.fp-toggle {
  font-size: 12px;
}
.fp-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 12px;
  color: #455a64;
}
.fp-legend .lg-end {
  font-size: 11px;
  color: var(--lot-muted);
  white-space: nowrap;
}
.fp-note {
  display: flex;
  align-items: flex-start;
  margin-top: 8px;
  font-size: 11.5px;
  line-height: 1.35;
  color: var(--lot-faint);
}
.fp-note--indent {
  margin-top: 3px;
  margin-left: 2px;
}
.fp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.fp-footer {
  display: flex;
  justify-content: flex-end;
  padding: 8px 12px;
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
