<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import { COLOR_MODE_OPTIONS, USE_CLASS_OPTIONS, useFiltersStore } from '@/stores/filters'

const store = useFiltersStore()
const { vacantOnly, useClasses, colorMode, activeCount } = storeToRefs(store)
const open = ref(true)
</script>

<template>
  <q-card class="filter-panel" flat bordered>
    <q-card-section class="row items-center q-py-sm q-px-md">
      <q-icon name="tune" size="20px" class="q-mr-sm text-primary" />
      <div class="text-subtitle2">Map controls</div>
      <q-badge v-if="activeCount" color="primary" class="q-ml-sm">{{ activeCount }}</q-badge>
      <q-space />
      <q-btn
        flat
        dense
        round
        size="sm"
        :icon="open ? 'expand_less' : 'expand_more'"
        @click="open = !open"
      />
    </q-card-section>

    <q-slide-transition>
      <div v-show="open">
        <q-separator />
        <q-card-section class="q-py-sm q-px-md">
          <div class="text-caption text-grey-7 q-mb-xs">Color lots by</div>
          <q-btn-toggle
            v-model="colorMode"
            spread
            no-caps
            dense
            unelevated
            toggle-color="primary"
            color="grey-3"
            text-color="grey-9"
            :options="COLOR_MODE_OPTIONS"
          />

          <div class="legend q-mt-sm">
            <template v-if="colorMode === 'vacancy'">
              <span class="dot" style="background: #f9a825" /> Vacant
              <span class="dot q-ml-md" style="background: #1565c0" /> Built
            </template>
            <template v-else>
              <span class="text-caption text-grey-7">{{
                colorMode === 'opportunity' ? 'Low' : 'Lower risk'
              }}</span>
              <span
                class="gradient"
                :style="{
                  background:
                    colorMode === 'opportunity'
                      ? 'linear-gradient(90deg,#c62828,#f9a825,#9ccc65,#2e7d32)'
                      : 'linear-gradient(90deg,#2e7d32,#9ccc65,#f9a825,#c62828)',
                }"
              />
              <span class="text-caption text-grey-7">{{
                colorMode === 'opportunity' ? 'High' : 'Higher risk'
              }}</span>
            </template>
          </div>
          <div v-if="colorMode !== 'vacancy'" class="text-caption text-grey-6 q-mt-xs">
            Scored vacant lots only
          </div>
          <div class="text-caption text-grey-6 q-mt-xs row items-center">
            <q-icon name="place" size="14px" class="q-mr-xs" />Pins mark vacant lots, shaded red→green
            by opportunity
          </div>

          <q-separator class="q-my-sm" />

          <q-toggle v-model="vacantOnly" label="Vacant lots only" dense color="amber-8" />

          <div class="text-caption text-grey-7 q-mt-sm q-mb-xs">Zoning use class</div>
          <div class="row q-gutter-xs">
            <q-chip
              v-for="option in USE_CLASS_OPTIONS"
              :key="option.value"
              clickable
              dense
              :color="useClasses.includes(option.value) ? 'primary' : 'grey-3'"
              :text-color="useClasses.includes(option.value) ? 'white' : 'grey-9'"
              @click="store.toggleClass(option.value)"
            >
              <span class="dot q-mr-xs" :style="{ background: option.color }" />
              {{ option.label }}
            </q-chip>
          </div>

          <div class="row justify-end q-mt-sm">
            <q-btn flat dense size="sm" color="grey-7" label="Reset" @click="store.reset()" />
          </div>
        </q-card-section>
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
  width: 290px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
}
.legend {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #455a64;
}
.gradient {
  flex: 1;
  height: 10px;
  border-radius: 5px;
}
</style>
