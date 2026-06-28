<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PricingPlans from '@/components/PricingPlans.vue'
import { ApiError, api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

const store = useAuthStore()
const { user, usage } = storeToRefs(store)
const router = useRouter()
const route = useRoute()

const checkoutNotice = ref<'success' | 'cancel' | null>(null)
const portalLoading = ref(false)
const portalError = ref<string | null>(null)
const digestSaving = ref(false)

const isPaid = computed(() => (user.value?.tier ?? 'free') !== 'free')

const DIGEST_OPTIONS = [
  { label: 'Weekly', value: 'weekly' as const },
  { label: 'Daily', value: 'daily' as const },
  { label: 'Off', value: 'off' as const },
]

const digestFrequency = computed({
  get: () => user.value?.digest_frequency ?? 'weekly',
  set: (value: 'off' | 'weekly' | 'daily') => {
    digestSaving.value = true
    void store
      .setDigest(value)
      .finally(() => {
        digestSaving.value = false
      })
  },
})

onMounted(async () => {
  const flag = route.query.checkout
  if (flag === 'success' || flag === 'cancel') checkoutNotice.value = flag
  await store.refreshUser()
  await store.fetchUsage()
})

async function manageBilling(): Promise<void> {
  portalError.value = null
  portalLoading.value = true
  try {
    const { url } = await api.createPortal()
    window.location.href = url
  } catch (cause) {
    portalError.value = cause instanceof ApiError ? cause.message : 'Could not open billing portal.'
  } finally {
    portalLoading.value = false
  }
}

const metrics = computed(() => {
  if (!usage.value) return []
  return [
    { key: 'views', label: 'Parcels viewed today', icon: 'map', ...usage.value.parcel_views },
    { key: 'ask', label: 'AI questions today', icon: 'forum', ...usage.value.ask },
  ]
})

function ratio(used: number, limit: number | null): number {
  if (limit === null || limit === 0) return 0
  return Math.min(1, used / limit)
}

function barColor(used: number, limit: number | null): string {
  const r = ratio(used, limit)
  return r >= 1 ? 'negative' : r >= 0.8 ? 'warning' : 'primary'
}

async function signOut(): Promise<void> {
  store.logout()
  await router.push('/')
}
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat dense round icon="arrow_back" to="/" aria-label="Back to map" />
        <q-toolbar-title>Account</q-toolbar-title>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="column items-center q-pa-md q-gutter-md">
        <q-banner
          v-if="checkoutNotice === 'success'"
          dense
          class="account-card bg-green-1 text-positive rounded-borders"
        >
          <template #avatar><q-icon name="check_circle" color="positive" /></template>
          Payment received — your plan will update within a moment.
        </q-banner>
        <q-banner
          v-else-if="checkoutNotice === 'cancel'"
          dense
          class="account-card bg-grey-2 text-grey-8 rounded-borders"
        >
          <template #avatar><q-icon name="info" color="grey-7" /></template>
          Checkout canceled — no charge was made.
        </q-banner>

        <q-card v-if="user" flat bordered class="account-card">
          <q-card-section class="row items-center q-gutter-md">
            <q-avatar size="56px" color="primary" text-color="white" class="text-h5 text-weight-bold">
              {{ user.email.charAt(0).toUpperCase() }}
            </q-avatar>
            <div>
              <div class="text-h6">{{ user.full_name ?? user.email }}</div>
              <div class="text-grey-7">{{ user.email }}</div>
            </div>
            <q-space />
            <q-chip color="primary" text-color="white" class="text-capitalize">
              {{ user.tier }} plan
            </q-chip>
          </q-card-section>

          <q-separator />

          <q-card-section v-if="usage" class="q-gutter-md">
            <div v-for="m in metrics" :key="m.key">
              <div class="row items-center">
                <q-icon :name="m.icon" size="18px" color="grey-7" class="q-mr-xs" />
                <div class="text-overline text-grey-7">{{ m.label }}</div>
                <q-space />
                <div v-if="m.remaining !== null" class="text-caption text-grey-7">
                  {{ m.remaining }} left
                </div>
              </div>
              <div class="row items-baseline">
                <div class="text-h6 text-weight-bold">{{ m.used }}</div>
                <div class="text-subtitle2 text-grey-7 q-ml-xs">
                  / {{ m.limit === null ? 'unlimited' : m.limit }}
                </div>
              </div>
              <q-linear-progress
                v-if="m.limit !== null"
                :value="ratio(m.used, m.limit)"
                size="9px"
                rounded
                class="q-mt-xs"
                :color="barColor(m.used, m.limit)"
                track-color="grey-3"
              />
            </div>
            <div class="text-caption text-grey-6">Limits reset daily.</div>
          </q-card-section>
          <q-card-section v-else class="text-body2 text-grey-6">Loading usage…</q-card-section>

          <q-separator />

          <q-card-section>
            <div class="row items-center q-mb-xs">
              <q-icon name="mail" size="18px" color="grey-7" class="q-mr-xs" />
              <div class="text-subtitle2">Email digest of watchlist updates</div>
              <q-space />
              <q-spinner v-if="digestSaving" size="16px" color="primary" />
            </div>
            <div class="text-caption text-grey-7 q-mb-sm">
              Get an email when your saved lots change (tax, L&amp;I, price, status).
            </div>
            <q-btn-toggle
              v-model="digestFrequency"
              spread
              no-caps
              dense
              unelevated
              rounded
              toggle-color="primary"
              color="grey-2"
              text-color="grey-9"
              :options="DIGEST_OPTIONS"
            />
          </q-card-section>

          <q-separator />

          <q-card-section v-if="isPaid">
            <div class="row items-center">
              <div>
                <div class="text-subtitle2">Billing</div>
                <div class="text-caption text-grey-7">
                  Update payment, switch plans, or cancel anytime.
                </div>
                <div v-if="portalError" class="text-caption text-negative q-mt-xs">
                  {{ portalError }}
                </div>
              </div>
              <q-space />
              <q-btn
                outline
                color="primary"
                no-caps
                icon="credit_card"
                label="Manage billing"
                :loading="portalLoading"
                @click="manageBilling"
              />
            </div>
          </q-card-section>

          <q-separator />

          <q-card-actions align="right">
            <q-btn flat no-caps color="negative" icon="logout" label="Sign out" @click="signOut" />
          </q-card-actions>
        </q-card>

        <q-card v-if="!isPaid" flat bordered class="pricing-card">
          <q-card-section class="text-center">
            <div class="text-h6">Upgrade your plan</div>
            <div class="text-body2 text-grey-7">Unlock unlimited verdicts and more AI questions.</div>
          </q-card-section>
          <q-card-section>
            <PricingPlans />
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.account-card {
  width: 520px;
  max-width: 94vw;
  border-radius: 14px;
}
.pricing-card {
  width: 960px;
  max-width: 94vw;
  border-radius: 14px;
}
</style>
