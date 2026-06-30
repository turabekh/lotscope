<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { useParcelStore } from '@/stores/parcel'

const { historic } = storeToRefs(useParcelStore())

const show = computed(() => historic.value?.in_historic_district === true)
</script>

<template>
  <q-card v-if="show && historic" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="account_balance" size="18px" class="q-mr-xs" />Historic district
        <q-icon name="info" size="14px" class="q-ml-xs text-grey-5" />
        <q-tooltip max-width="260px" anchor="bottom middle" self="top middle">
          The parcel sits in a Philadelphia Register historic district. Informational — confirm
          scope with the Historical Commission.
        </q-tooltip>
        <q-space />
        <q-chip dense square color="deep-orange-7" text-color="white" icon="account_balance">
          Review required
        </q-chip>
      </div>

      <div class="text-body2 text-weight-medium text-grey-9">
        {{ historic.district_name }}
        <span v-if="historic.designated_date" class="text-grey-6 text-caption">
          · designated {{ historic.designated_date }}
        </span>
      </div>

      <div v-if="historic.note" class="text-body2 text-grey-7 q-mt-xs">{{ historic.note }}</div>
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
