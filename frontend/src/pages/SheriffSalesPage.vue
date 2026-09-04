<script setup lang="ts">
import { useQuasar } from 'quasar'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { SheriffSaleItem, SheriffSalesResponse } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const $q = useQuasar()
const router = useRouter()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const SHERIFF_TIERS = ['pro', 'investor', 'enterprise']
const hasAccess = computed(() => SHERIFF_TIERS.includes(user.value?.tier ?? 'free'))

const zip = ref('')
const result = ref<SheriffSalesResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  if (!hasAccess.value) return
  loading.value = true
  error.value = null
  try {
    result.value = await api.getSheriffSales({
      zip: zip.value.trim() || undefined,
      limit: 200,
    })
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load sheriff sales.'
  } finally {
    loading.value = false
  }
}

const monthGroups = computed(() => {
  const groups = new Map<string, SheriffSaleItem[]>()
  for (const item of result.value?.items ?? []) {
    const key = item.sale_date
      ? new Date(item.sale_date).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
      : 'Date to be announced'
    const bucket = groups.get(key)
    if (bucket) bucket.push(item)
    else groups.set(key, [item])
  }
  return [...groups.entries()].map(([month, items]) => ({ month, items }))
})

async function downloadIcs(): Promise<void> {
  try {
    await api.downloadSheriffIcs()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : 'Could not download the calendar feed.'
  }
}

async function copySubscribeUrl(): Promise<void> {
  try {
    const { url } = await api.getSheriffSubscribeUrl()
    await navigator.clipboard.writeText(url)
    $q.notify({
      type: 'positive',
      message: 'Subscription link copied — add it as a calendar subscription in your calendar app.',
    })
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : 'Could not create the subscription link.'
  }
}

function openItem(item: SheriffSaleItem): void {
  void router.push({ name: 'parcel', params: { id: item.parcel_number } })
}

function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(iso)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
}

function countdownLabel(iso: string | null): string {
  const days = daysUntil(iso)
  if (days === null) return 'Date TBD'
  if (days < 0) return 'Past'
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  return `In ${days} days`
}

function countdownColor(iso: string | null): string {
  const days = daysUntil(iso)
  if (days === null || days < 0) return 'grey-5'
  if (days <= 7) return 'negative'
  if (days <= 30) return 'warning'
  return 'primary'
}

function money(value: number | null): string {
  return value === null ? '—' : `$${Math.round(value).toLocaleString('en-US')}`
}

onMounted(() => {
  if (hasAccess.value) void load()
})
</script>

<template>
  <q-page class="q-pa-md">
    <div class="sheriff-wrap">
      <div v-if="!hasAccess" class="upgrade">
        <q-icon name="gavel" size="52px" color="grey-4" />
        <div class="text-h6 q-mt-md">The Sheriff-sale calendar is a Pro feature</div>
        <div class="text-body2 text-grey-7 q-mb-md">
          Track upcoming tax and mortgage foreclosure auctions, ranked by how far each opening bid
          sits below its max allowable offer.
        </div>
        <q-btn unelevated no-caps color="primary" label="Upgrade" :to="{ name: 'account' }" />
      </div>

      <template v-else>
        <div class="row items-end q-col-gutter-md q-mb-md">
          <div class="col-auto">
            <div class="text-caption text-grey-7 q-mb-xs">ZIP</div>
            <q-input
              v-model="zip"
              outlined
              dense
              clearable
              placeholder="e.g. 19146"
              style="min-width: 160px"
              @keyup.enter="load"
              @clear="load"
            >
              <template #append>
                <q-btn flat dense round icon="search" @click="load" />
              </template>
            </q-input>
          </div>
          <div class="col-auto">
            <q-btn-group outline>
              <q-btn
                outline
                no-caps
                color="primary"
                icon="download"
                label="Download .ics"
                :disable="!result || result.items.length === 0"
                @click="downloadIcs"
              />
              <q-btn
                outline
                no-caps
                color="primary"
                icon="event_repeat"
                label="Subscribe"
                @click="copySubscribeUrl"
              >
                <q-tooltip
                  >Copy a personal subscription link to add in your calendar app.</q-tooltip
                >
              </q-btn>
            </q-btn-group>
          </div>
        </div>

        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
          {{ error }}
        </q-banner>

        <q-inner-loading :showing="loading" color="primary" />

        <template v-if="result && result.items.length">
          <div v-for="group in monthGroups" :key="group.month" class="q-mb-md">
            <div class="text-subtitle2 text-grey-7 q-mb-xs">{{ group.month }}</div>
            <q-list bordered separator class="rounded-borders">
              <q-item
                v-for="item in group.items"
                :key="item.case_number"
                v-ripple
                clickable
                @click="openItem(item)"
              >
                <q-item-section avatar>
                  <q-chip dense square :color="countdownColor(item.sale_date)" text-color="white">
                    {{ countdownLabel(item.sale_date) }}
                  </q-chip>
                </q-item-section>
                <q-item-section>
                  <q-item-label class="ellipsis">
                    {{ item.address ?? item.parcel_number }}
                  </q-item-label>
                  <q-item-label caption class="ellipsis">
                    {{ item.sale_type ?? 'Sale' }} · {{ item.case_number }}
                    <span v-if="item.plaintiff"> · {{ item.plaintiff }}</span>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row items-center q-gutter-xs">
                    <q-badge v-if="item.bid_gap !== null" color="positive" outline>
                      Gap {{ money(item.bid_gap) }}
                    </q-badge>
                    <q-badge v-if="item.opportunity_score !== null" color="primary" outline>
                      {{ item.opportunity_score }}
                    </q-badge>
                  </div>
                  <div class="text-caption text-grey-6 q-mt-xs">
                    Bid {{ money(item.opening_bid) }}
                  </div>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </template>

        <div v-else-if="result && !loading" class="empty">
          <q-icon name="event_busy" size="40px" color="grey-4" />
          <div class="text-body1 q-mt-sm">No upcoming {{ result.label.toLowerCase() }}</div>
          <div class="text-caption text-grey-6">
            {{ result.note ?? 'Clear the ZIP filter to see the full calendar.' }}
          </div>
        </div>

        <div
          v-if="result && result.returned < result.total"
          class="text-caption text-grey-6 q-mt-sm"
        >
          Showing {{ result.returned }} of {{ result.total }} scheduled sales.
        </div>
      </template>
    </div>
  </q-page>
</template>

<style scoped>
.sheriff-wrap {
  max-width: 860px;
  margin: 0 auto;
  position: relative;
}
.upgrade,
.empty {
  text-align: center;
  padding: 56px 20px;
}
</style>
