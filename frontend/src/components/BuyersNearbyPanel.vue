<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import UpgradePrompt from '@/components/UpgradePrompt.vue'
import { ApiError, api } from '@/lib/api'
import type { BuyersNearby, NearbyBuyer } from '@/lib/types'
import { useMarketStore } from '@/stores/market'
import { useParcelStore } from '@/stores/parcel'

const router = useRouter()
const market = useMarketStore()
const store = useParcelStore()
const { detail } = storeToRefs(store)

const result = ref<BuyersNearby | null>(null)
const gated = ref(false)
const loading = ref(false)

const topBuyers = computed<NearbyBuyer[]>(() => (result.value?.buyers ?? []).slice(0, 5))

function money(value: number | null): string {
  return value === null ? '—' : `$${Math.round(value).toLocaleString()}`
}

async function load(parcelNumber: string | undefined): Promise<void> {
  result.value = null
  gated.value = false
  if (!parcelNumber) return
  loading.value = true
  try {
    result.value = await api.getParcelBuyers(parcelNumber)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 429) {
      gated.value = true
    }
  } finally {
    loading.value = false
  }
}

function openBuyer(buyer: NearbyBuyer): void {
  void router.push({
    name: 'buyer-profile',
    params: { market: market.active, buyerKey: buyer.buyer_key },
  })
}

watch(() => detail.value?.parcel_number, load, { immediate: true })
</script>

<template>
  <div v-if="gated" class="panel">
    <UpgradePrompt cap="buyer_intel" variant="card" />
  </div>

  <div v-else-if="result && !result.available" class="panel unavailable">
    <q-icon name="lock" size="20px" color="grey-6" />
    <span class="text-caption text-grey-7">{{ result.note }}</span>
  </div>

  <div v-else-if="result && topBuyers.length" class="panel">
    <div class="panel-head">
      <q-icon name="real_estate_agent" size="20px" color="primary" />
      <span class="text-subtitle2">Active lot buyers nearby</span>
      <q-badge color="primary" outline>{{ result.buyers.length }}</q-badge>
    </div>
    <q-list dense separator class="rounded-borders">
      <q-item
        v-for="buyer in topBuyers"
        :key="buyer.buyer_key"
        v-ripple
        clickable
        @click="openBuyer(buyer)"
      >
        <q-item-section>
          <q-item-label>{{ buyer.display_name }}</q-item-label>
          <q-item-label caption>
            {{ buyer.lot_purchases_window }} lots · median {{ money(buyer.median_price) }}
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-icon name="chevron_right" color="grey-5" />
        </q-item-section>
      </q-item>
    </q-list>
    <router-link
      class="all-link"
      :to="{ name: 'buyers', params: { market: market.active } }"
    >
      See all active buyers →
    </router-link>
  </div>
</template>

<style scoped>
.panel {
  margin-bottom: 14px;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.unavailable {
  display: flex;
  align-items: center;
  gap: 8px;
}
.all-link {
  display: inline-block;
  margin-top: 8px;
  font-size: 12px;
  color: var(--q-primary);
  text-decoration: none;
}
</style>
