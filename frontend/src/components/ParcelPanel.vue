<script setup lang="ts">
import { storeToRefs } from 'pinia'

import AskBox from '@/components/AskBox.vue'
import VerdictPanel from '@/components/VerdictPanel.vue'
import { formatCurrency } from '@/lib/format'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { detail, verdict, loading, error } = storeToRefs(store)

function yesNo(value: boolean | null): string {
  if (value === null) return '—'
  return value ? 'yes' : 'no'
}
</script>

<template>
  <div class="q-pa-md relative-position">
    <q-inner-loading :showing="loading" />
    <q-banner v-if="error" class="bg-red-1 text-negative">{{ error }}</q-banner>
    <template v-if="detail">
      <div class="text-h6">{{ detail.address ?? detail.parcel_number }}</div>
      <div class="text-caption text-grey">
        Parcel {{ detail.parcel_number }} · {{ detail.base_zoning_code ?? 'zoning unknown' }}
      </div>
      <q-list dense class="q-my-md">
        <q-item>
          <q-item-section>Owner</q-item-section>
          <q-item-section side>{{ detail.owner ?? '—' }}</q-item-section>
        </q-item>
        <q-item>
          <q-item-section>Lot area</q-item-section>
          <q-item-section side>{{ detail.lot_area_sqft ?? '—' }} sqft</q-item-section>
        </q-item>
        <q-item>
          <q-item-section>Assessed value</q-item-section>
          <q-item-section side>{{ formatCurrency(detail.market_value) }}</q-item-section>
        </q-item>
        <q-item>
          <q-item-section>Vacant</q-item-section>
          <q-item-section side>{{ yesNo(detail.is_vacant) }}</q-item-section>
        </q-item>
      </q-list>
      <q-btn
        dense
        color="primary"
        label="Refresh verdict"
        class="q-mb-md"
        @click="store.refreshVerdict()"
      />
      <VerdictPanel v-if="verdict" :verdict="verdict" />
      <q-banner v-else dense class="bg-grey-2 q-mb-md">
        No verdict yet — refresh to compute one.
      </q-banner>
      <AskBox :parcel-number="detail.parcel_number" />
    </template>
    <div v-else-if="!loading" class="text-grey text-center q-pa-xl">
      Search for a parcel to see its verdict.
    </div>
  </div>
</template>
