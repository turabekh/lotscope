<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const { historic } = storeToRefs(useParcelStore())

const inDistrict = computed(() => historic.value?.in_historic_district === true)

const checkedAndClear = computed(
  () => historic.value?.evaluated === true && historic.value.in_historic_district === false,
)

const unevaluated = computed(() => historic.value?.evaluated === false)

const show = computed(() => inDistrict.value || checkedAndClear.value || unevaluated.value)

const style = computed(() => {
  if (inDistrict.value) {
    return { label: 'Review required', color: 'deep-orange-7', icon: 'account_balance' }
  }
  if (checkedAndClear.value) {
    return { label: 'Not designated', color: 'grey-7', icon: 'check' }
  }
  return { label: 'Not checked', color: 'blue-grey-5', icon: 'help_outline' }
})
</script>

<template>
  <q-card v-if="show && historic" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="account_balance" size="18px" class="q-mr-xs" />Historic district
        <q-icon name="info" size="14px" class="q-ml-xs lot-text-faint" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          Whether the parcel sits in a Philadelphia Register historic district. Informational —
          confirm scope with the Historical Commission.
        </q-tooltip>
        <q-space />
        <q-chip dense square :color="style.color" text-color="white" :icon="style.icon">
          {{ style.label }}
        </q-chip>
      </div>

      <template v-if="inDistrict">
        <div class="text-body2 text-weight-medium lot-text-ink">
          {{ historic.district_name }}
          <span v-if="historic.designated_date" class="lot-text-faint text-caption">
            · designated {{ historic.designated_date }}
          </span>
        </div>

        <div v-if="historic.note" class="text-body2 lot-text-muted q-mt-xs">
          {{ historic.note }}
        </div>
      </template>

      <div v-else-if="checkedAndClear" class="text-body2 lot-text-muted">
        Not in a designated historic district.
      </div>

      <template v-else>
        <div class="text-body2 lot-text-muted">
          Historic district status could not be checked for this lot.
        </div>
        <div class="text-caption lot-text-muted q-mt-xs">
          This is a gap in what we hold, not a finding about the lot.
        </div>
      </template>
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
