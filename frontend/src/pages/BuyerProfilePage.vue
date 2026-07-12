<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { BuyerProfileDetail, BuyerPurchase } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'

const route = useRoute()
const router = useRouter()
const market = useMarketStore()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const INVESTOR_TIERS = ['investor', 'enterprise']
const hasAccess = computed(() => INVESTOR_TIERS.includes(user.value?.tier ?? 'free'))

const profile = ref<BuyerProfileDetail | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const buyerKey = computed(() => String(route.params.buyerKey ?? ''))

function money(value: number | null): string {
  return value === null ? '—' : `$${Math.round(value).toLocaleString()}`
}

function when(value: string | null): string {
  return value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
}

async function load(): Promise<void> {
  if (!hasAccess.value || !buyerKey.value) return
  loading.value = true
  error.value = null
  try {
    profile.value = await api.getBuyer(market.active, buyerKey.value)
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load this buyer.'
  } finally {
    loading.value = false
  }
}

function openParcel(purchase: BuyerPurchase): void {
  void router.push({ name: 'parcel', params: { market: market.active, id: purchase.parcel_number } })
}

onMounted(load)
watch(buyerKey, load)
</script>

<template>
  <q-page class="q-pa-md">
    <div class="profile-wrap">
      <q-btn flat dense no-caps icon="arrow_back" label="Buyers" :to="{ name: 'buyers', params: { market: market.active } }" class="q-mb-sm" />

      <div v-if="!hasAccess" class="empty">
        <q-icon name="lock" size="40px" color="grey-5" />
        <div class="text-body1 q-mt-sm">Cash-buyer intelligence is an Investor feature.</div>
      </div>

      <q-banner v-else-if="error" dense class="bg-red-1 text-negative rounded-borders">
        {{ error }}
      </q-banner>

      <template v-else-if="profile">
        <div class="text-h6">{{ profile.display_name }}</div>
        <div class="text-caption text-grey-7 q-mb-md">
          {{ profile.mailing_address ?? 'No mailing address on record' }}
        </div>

        <div class="stats q-mb-md">
          <q-card flat bordered class="stat">
            <div class="text-h6">{{ profile.lot_purchases_window }}</div>
            <div class="text-caption text-grey-7">Vacant lots (24mo)</div>
          </q-card>
          <q-card flat bordered class="stat">
            <div class="text-h6">{{ profile.purchases_window }}</div>
            <div class="text-caption text-grey-7">All purchases (24mo)</div>
          </q-card>
          <q-card flat bordered class="stat">
            <div class="text-h6">{{ money(profile.median_price) }}</div>
            <div class="text-caption text-grey-7">Median lot price</div>
          </q-card>
          <q-card flat bordered class="stat">
            <div class="text-h6">{{ money(profile.total_consideration) }}</div>
            <div class="text-caption text-grey-7">Total consideration</div>
          </q-card>
        </div>

        <div class="text-subtitle2 q-mb-xs">Recent purchases</div>
        <q-list bordered separator class="rounded-borders">
          <q-item
            v-for="purchase in profile.purchases"
            :key="purchase.parcel_number"
            v-ripple
            clickable
            @click="openParcel(purchase)"
          >
            <q-item-section>
              <q-item-label>{{ purchase.address ?? purchase.parcel_number }}</q-item-label>
              <q-item-label caption>{{ when(purchase.sale_date) }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <div class="text-body2">{{ money(purchase.sale_price) }}</div>
              <q-badge v-if="purchase.is_vacant" color="grey-3" text-color="grey-8">lot</q-badge>
            </q-item-section>
          </q-item>
        </q-list>
      </template>

      <q-inner-loading :showing="loading" color="primary" />
    </div>
  </q-page>
</template>

<style scoped>
.profile-wrap {
  max-width: 780px;
  margin: 0 auto;
  position: relative;
}
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.stat {
  padding: 14px 16px;
}
.empty {
  text-align: center;
  padding: 56px 20px;
}
</style>
