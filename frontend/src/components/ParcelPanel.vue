<script setup lang="ts">
import { storeToRefs } from 'pinia'

import AskBox from '@/components/AskBox.vue'
import PropertyFacts from '@/components/PropertyFacts.vue'
import VerdictPanel from '@/components/VerdictPanel.vue'
import { useParcelStore } from '@/stores/parcel'

const store = useParcelStore()
const { detail, verdict, loading, error } = storeToRefs(store)
</script>

<template>
  <div class="panel-root">
    <q-inner-loading :showing="loading" color="primary" />

    <template v-if="detail">
      <div class="panel-header">
        <div class="text-h6 ellipsis-2">{{ detail.address ?? detail.parcel_number }}</div>
        <div class="text-caption text-grey-3">Parcel {{ detail.parcel_number }}</div>
        <div class="q-gutter-xs q-mt-sm">
          <q-chip dense color="white" text-color="primary" class="text-weight-bold">
            {{ detail.base_zoning_code ?? 'No zoning' }}
          </q-chip>
          <q-chip v-if="detail.is_vacant" dense color="amber-8" text-color="white" icon="grass">
            Vacant
          </q-chip>
          <q-chip v-if="detail.is_city_owned" dense color="deep-orange" text-color="white" icon="account_balance">
            City-owned
          </q-chip>
        </div>
      </div>

      <div class="panel-body q-pa-md q-gutter-md">
        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders">
          {{ error }}
        </q-banner>

        <template v-if="verdict">
          <VerdictPanel :verdict="verdict" />
        </template>
        <q-banner v-else-if="!loading" dense class="bg-grey-2 rounded-borders">
          <template #avatar><q-icon name="info" color="grey-7" /></template>
          No verdict yet.
          <template #action>
            <q-btn flat dense color="primary" label="Compute" @click="store.refreshVerdict()" />
          </template>
        </q-banner>

        <PropertyFacts :detail="detail" />

        <div class="text-center">
          <q-btn
            flat
            dense
            no-caps
            color="grey-7"
            icon="refresh"
            label="Recompute verdict"
            :loading="loading"
            @click="store.refreshVerdict()"
          />
        </div>

        <AskBox :parcel-number="detail.parcel_number" />
      </div>
    </template>

    <div v-else-if="!loading" class="empty-state">
      <q-icon name="travel_explore" size="56px" color="grey-4" />
      <div class="text-subtitle1 text-grey-7 q-mt-md">Find a parcel</div>
      <div class="text-body2 text-grey-6">
        Search by address, owner, or parcel number — or click any lot on the map — to see its
        buildability, value, and risk verdict.
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel-root {
  position: relative;
  height: 100%;
  overflow-y: auto;
}
.panel-header {
  background: linear-gradient(135deg, #1565c0, #1976d2);
  color: white;
  padding: 16px;
}
.panel-body {
  padding-bottom: 32px;
}
.ellipsis-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.25;
}
.empty-state {
  text-align: center;
  padding: 48px 28px;
}
</style>
