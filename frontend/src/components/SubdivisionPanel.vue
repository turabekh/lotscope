<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const { subdivision } = storeToRefs(useParcelStore())

const show = computed(
  () =>
    subdivision.value !== null &&
    (subdivision.value.can_subdivide || subdivision.value.needs_consolidation),
)

const style = computed(() => {
  const value = subdivision.value
  if (value === null) return { label: '', color: 'blue-grey-6', icon: 'crop_free' }
  if (value.can_subdivide) {
    return { label: `Splits into ${value.max_lots} lots`, color: 'positive', icon: 'call_split' }
  }
  return { label: 'Consolidation candidate', color: 'warning', icon: 'merge' }
})

const reason = computed(() => subdivision.value?.reasons[0] ?? '')
</script>

<template>
  <q-card v-if="show && subdivision" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="dashboard_customize" size="18px" class="q-mr-xs" />Subdivision potential
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          Compares lot size to the district's minimum lot area and width to estimate how many
          conforming lots it could split into, or whether it needs consolidation. Informational;
          subject to plan approval.
        </q-tooltip>
        <q-space />
        <q-chip dense square :color="style.color" text-color="white" :icon="style.icon">
          {{ style.label }}
        </q-chip>
      </div>

      <div v-if="reason" class="text-body2 text-grey-7 q-mt-xs">{{ reason }}</div>

      <div v-if="subdivision.district_code" class="text-caption text-grey-5 q-mt-sm">
        {{ subdivision.district_code }} minimums: {{ subdivision.min_lot_area_sqft ?? '—' }} sq ft
        area, {{ subdivision.min_lot_width_ft ?? '—' }} ft width
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
</style>
