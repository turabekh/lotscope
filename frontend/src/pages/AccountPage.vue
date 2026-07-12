<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PricingPlans from '@/components/PricingPlans.vue'
import { ApiError, api } from '@/lib/api'
import type { CreditPackKey } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useCreditsStore } from '@/stores/credits'
import { usePushStore } from '@/stores/push'

const store = useAuthStore()
const { user, usage } = storeToRefs(store)
const credits = useCreditsStore()
const { balance: creditBalance } = storeToRefs(credits)
const push = usePushStore()

const CREDIT_PACKS: { key: CreditPackKey; credits: number; price: string }[] = [
  { key: 'small', credits: 25, price: '$12.50' },
  { key: 'medium', credits: 100, price: '$40' },
  { key: 'large', credits: 500, price: '$175' },
]
const buyingPack = ref<CreditPackKey | null>(null)

async function buyCredits(pack: CreditPackKey): Promise<void> {
  buyingPack.value = pack
  try {
    const { url } = await api.buyCredits(pack)
    window.location.href = url
  } catch (cause) {
    portalError.value = cause instanceof ApiError ? cause.message : 'Could not start checkout.'
  } finally {
    buyingPack.value = null
  }
}
const {
  supported: pushSupported,
  enabled: pushEnabled,
  busy: pushBusy,
  error: pushError,
} = storeToRefs(push)
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
    void store.setDigest(value).finally(() => {
      digestSaving.value = false
    })
  },
})

const signer = ref({ entity_name: '', signer_name: '', signer_phone: '', signer_email: '' })
const signerSaving = ref(false)
const signerSaved = ref(false)

function loadSigner(): void {
  signer.value = {
    entity_name: user.value?.entity_name ?? '',
    signer_name: user.value?.signer_name ?? '',
    signer_phone: user.value?.signer_phone ?? '',
    signer_email: user.value?.signer_email ?? '',
  }
}

async function saveSigner(): Promise<void> {
  signerSaving.value = true
  signerSaved.value = false
  try {
    await store.setSigner({
      entity_name: signer.value.entity_name || null,
      signer_name: signer.value.signer_name || null,
      signer_phone: signer.value.signer_phone || null,
      signer_email: signer.value.signer_email || null,
    })
    signerSaved.value = true
  } finally {
    signerSaving.value = false
  }
}

onMounted(async () => {
  const flag = route.query.checkout
  if (flag === 'success' || flag === 'cancel') checkoutNotice.value = flag
  await store.refreshUser()
  loadSigner()
  await store.fetchUsage()
  await push.refresh()
  await credits.ensureLoaded()
})

function togglePush(value: boolean): void {
  void (value ? push.enable() : push.disable())
}

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

      <q-card-section>
        <div class="row items-center q-mb-xs">
          <q-icon name="draw" size="18px" color="grey-7" class="q-mr-xs" />
          <div class="text-subtitle2">Offer signer profile</div>
          <q-space />
          <span v-if="signerSaved" class="text-caption text-positive">Saved</span>
        </div>
        <div class="text-caption text-grey-7 q-mb-sm">
          Defaulted onto every letter of intent you generate. Overridable per offer.
        </div>
        <div class="q-gutter-sm">
          <q-input v-model="signer.entity_name" outlined dense label="Entity / company" />
          <q-input v-model="signer.signer_name" outlined dense label="Signer name" />
          <div class="row q-col-gutter-sm">
            <q-input v-model="signer.signer_phone" outlined dense label="Phone" class="col" />
            <q-input v-model="signer.signer_email" outlined dense label="Email" class="col" />
          </div>
          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Save signer profile"
            :loading="signerSaving"
            @click="saveSigner"
          />
        </div>
      </q-card-section>

      <q-separator />

      <q-card-section>
        <div class="row items-center">
          <q-icon name="notifications" size="18px" color="grey-7" class="q-mr-xs" />
          <div>
            <div class="text-subtitle2">Browser push notifications</div>
            <div class="text-caption text-grey-7">
              Get a push on this device when your watched lots change.
            </div>
            <div v-if="pushError" class="text-caption text-negative q-mt-xs">{{ pushError }}</div>
          </div>
          <q-space />
          <q-toggle
            v-if="pushSupported"
            :model-value="pushEnabled"
            :disable="pushBusy"
            color="primary"
            @update:model-value="togglePush"
          />
          <q-chip v-else dense color="grey-3" text-color="grey-8">Not supported</q-chip>
        </div>
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

      <q-card-section>
        <div class="row items-center q-mb-sm">
          <div>
            <div class="text-subtitle2">Skip-trace credits</div>
            <div class="text-caption text-grey-7">
              Spend 1 credit to reveal an owner's phones and emails.
            </div>
          </div>
          <q-space />
          <q-chip square color="primary" text-color="white" icon="toll">
            {{ creditBalance ?? 0 }} credits
          </q-chip>
        </div>
        <div class="row q-gutter-sm">
          <q-btn
            v-for="pack in CREDIT_PACKS"
            :key="pack.key"
            outline
            no-caps
            color="primary"
            :label="`${pack.credits} · ${pack.price}`"
            :loading="buyingPack === pack.key"
            @click="buyCredits(pack.key)"
          />
        </div>
        <div class="text-caption text-grey-5 q-mt-xs">
          People-search data — not for credit, employment, insurance, or tenant-screening use.
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
