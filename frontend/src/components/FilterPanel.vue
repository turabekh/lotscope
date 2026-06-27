<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'

import { USE_CLASS_OPTIONS, useFiltersStore } from '@/stores/filters'

const store = useFiltersStore()
const { vacantOnly, useClasses, activeCount } = storeToRefs(store)
const open = ref(true)
</script>

<template>
  <q-card class="filter-panel" flat bordered>
    <q-card-section class="row items-center q-py-sm q-px-md">
      <q-icon name="tune" size="20px" class="q-mr-sm text-primary" />
      <div class="text-subtitle2">Filters</div>
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
          <q-toggle v-model="vacantOnly" label="Vacant lots only" dense color="amber-8" />

          <div class="text-caption text-grey-7 q-mt-md q-mb-xs">Zoning use class</div>
          <div class="row q-gutter-xs">
            <q-chip
              v-for="option in USE_CLASS_OPTIONS"
              :key="option.value"
              clickable
              dense
              :selected="useClasses.includes(option.value)"
              :color="useClasses.includes(option.value) ? 'primary' : 'grey-3'"
              :text-color="useClasses.includes(option.value) ? 'white' : 'grey-9'"
              @click="store.toggleClass(option.value)"
            >
              <span class="dot q-mr-xs" :style="{ background: option.color }" />
              {{ option.label }}
            </q-chip>
          </div>

          <div class="row items-center q-mt-md">
            <div class="legend-row text-caption text-grey-7">
              <span class="dot" style="background: #f9a825" /> Vacant
              <span class="dot q-ml-sm" style="background: #1565c0" /> Built
            </div>
            <q-space />
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
  width: 280px;
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
.legend-row {
  display: flex;
  align-items: center;
}
</style>
