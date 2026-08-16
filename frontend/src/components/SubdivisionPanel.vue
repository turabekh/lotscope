<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const { subdivision } = storeToRefs(useParcelStore())

const unevaluated = computed(
  () => subdivision.value !== null && subdivision.value.is_conforming === null,
)

const meetsMinimums = computed(
  () =>
    subdivision.value !== null &&
    subdivision.value.is_conforming === true &&
    !subdivision.value.can_subdivide &&
    !subdivision.value.needs_consolidation,
)

const show = computed(
  () =>
    subdivision.value !== null &&
    (subdivision.value.can_subdivide ||
      subdivision.value.needs_consolidation ||
      unevaluated.value ||
      meetsMinimums.value),
)

const style = computed(() => {
  const value = subdivision.value
  if (value === null) return { label: '', color: 'blue-grey-6', icon: 'crop_free' }
  if (unevaluated.value) {
    return { label: 'Not evaluated', color: 'blue-grey-5', icon: 'help_outline' }
  }
  if (meetsMinimums.value) {
    return { label: 'Too small to split', color: 'grey-7', icon: 'do_not_disturb_on' }
  }
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
        <q-icon name="info" size="14px" class="q-ml-xs lot-text-faint" />
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

      <div v-if="reason" class="text-body2 lot-text-muted q-mt-xs">{{ reason }}</div>

      <div v-if="unevaluated" class="text-caption lot-text-muted q-mt-xs">
        This is a gap in what we hold, not a finding about the lot.
      </div>

      <div v-if="subdivision.district_code" class="text-caption lot-text-muted q-mt-sm">
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
