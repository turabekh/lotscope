<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { BillingCadence, CheckoutTier, PlanInfo } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const { isAuthenticated } = storeToRefs(auth)
const router = useRouter()

const plans = ref<PlanInfo[]>([])
const contactUrl = ref('')
const cadence = ref<BillingCadence>('monthly')
const loading = ref(false)
const pendingTier = ref<string | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    const response = await api.getPlans()
    plans.value = response.plans
    contactUrl.value = response.contact_url
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load plans.'
  } finally {
    loading.value = false
  }
})

function priceLabel(plan: PlanInfo): string {
  const cents = cadence.value === 'monthly' ? plan.price_monthly_cents : plan.price_annual_cents
  if (cents === null) return 'Custom'
  if (cents === 0) return 'Free'
  return `$${Math.round(cents / 100)}`
}

function priceSuffix(plan: PlanInfo): string {
  if (plan.price_monthly_cents === null) return ''
  if (plan.price_monthly_cents === 0) return 'forever'
  return cadence.value === 'monthly' ? '/month' : '/year'
}

function annualSavingLabel(plan: PlanInfo): string | null {
  if (plan.price_monthly_cents === null || plan.price_annual_cents === null) return null
  if (plan.price_monthly_cents === 0) return null
  const fullYear = plan.price_monthly_cents * 12
  const saved = Math.round((fullYear - plan.price_annual_cents) / 100)
  return saved > 0 ? `Save $${saved}/yr` : null
}

const ctaFor = computed(() => {
  return (plan: PlanInfo): { label: string; color: string; disabled: boolean } => {
    if (plan.is_current && plan.tier === 'free') {
      return { label: 'Your plan', color: 'grey-6', disabled: true }
    }
    if (plan.is_current) {
      return { label: 'Manage billing', color: 'primary', disabled: false }
    }
    if (plan.action === 'contact') {
      return { label: 'Contact sales', color: 'dark', disabled: false }
    }
    if (plan.action === 'checkout') {
      return { label: `Upgrade to ${plan.name}`, color: 'primary', disabled: false }
    }
    return { label: 'Get started', color: 'primary', disabled: false }
  }
})

async function activate(plan: PlanInfo): Promise<void> {
  error.value = null
  if (plan.is_current && plan.tier === 'free') return

  if (plan.action === 'contact') {
    window.location.href = contactUrl.value
    return
  }

  if (!isAuthenticated.value) {
    await router.push({ name: plan.tier === 'free' ? 'register' : 'login', query: { redirect: '/account' } })
    return
  }

  pendingTier.value = plan.tier
  try {
    if (plan.is_current) {
      const { url } = await api.createPortal()
      window.location.href = url
      return
    }
    const { url } = await api.createCheckout(plan.tier as CheckoutTier, cadence.value)
    window.location.href = url
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not start checkout.'
  } finally {
    pendingTier.value = null
  }
}
</script>

<template>
  <div class="pricing">
    <div class="cadence-toggle">
      <q-btn-toggle
        v-model="cadence"
        unelevated
        no-caps
        rounded
        toggle-color="primary"
        color="grey-3"
        text-color="grey-8"
        :options="[
          { label: 'Monthly', value: 'monthly' },
          { label: 'Annual', value: 'annual' },
        ]"
      />
    </div>

    <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
      {{ error }}
    </q-banner>

    <div v-if="loading" class="row justify-center q-pa-lg">
      <q-spinner color="primary" size="32px" />
    </div>

    <div v-else class="plan-grid">
      <q-card
        v-for="plan in plans"
        :key="plan.tier"
        flat
        bordered
        class="plan-card"
        :class="{ featured: plan.tier === 'pro' }"
      >
        <q-badge v-if="plan.tier === 'pro'" color="primary" floating class="featured-badge">
          Most popular
        </q-badge>
        <q-card-section>
          <div class="text-overline text-grey-7">{{ plan.name }}</div>
          <div class="row items-baseline q-gutter-xs">
            <div class="text-h4 text-weight-bold">{{ priceLabel(plan) }}</div>
            <div class="text-subtitle2 text-grey-7">{{ priceSuffix(plan) }}</div>
          </div>
          <div
            v-if="cadence === 'annual' && annualSavingLabel(plan)"
            class="text-caption text-positive text-weight-medium"
          >
            {{ annualSavingLabel(plan) }}
          </div>
          <div class="text-body2 text-grey-7 q-mt-sm">{{ plan.tagline }}</div>
        </q-card-section>

        <q-separator />

        <q-card-section class="col-grow">
          <div v-for="item in plan.highlights" :key="item" class="row items-start q-mb-sm">
            <q-icon name="check_circle" color="primary" size="18px" class="q-mr-sm q-mt-xs" />
            <div class="text-body2">{{ item }}</div>
          </div>
        </q-card-section>

        <q-card-actions class="q-pa-md">
          <q-btn
            class="full-width"
            :unelevated="plan.tier === 'pro'"
            :outline="plan.tier !== 'pro'"
            no-caps
            :color="ctaFor(plan).color"
            :label="ctaFor(plan).label"
            :disable="ctaFor(plan).disabled"
            :loading="pendingTier === plan.tier"
            @click="activate(plan)"
          />
        </q-card-actions>
      </q-card>
    </div>
  </div>
</template>

<style scoped>
.cadence-toggle {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
@media (max-width: 1100px) {
  .plan-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
.plan-card {
  display: flex;
  flex-direction: column;
  border-radius: 16px;
}
.plan-card.featured {
  border-color: var(--q-primary);
  border-width: 2px;
  box-shadow: 0 12px 30px rgba(21, 101, 192, 0.15);
}
.featured-badge {
  border-radius: 8px;
}
@media (max-width: 800px) {
  .plan-grid {
    grid-template-columns: 1fr;
  }
}
</style>
