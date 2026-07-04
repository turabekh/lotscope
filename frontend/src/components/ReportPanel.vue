<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { ParcelReportResult } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ parcelNumber: string }>()

const auth = useAuthStore()
const { isAuthenticated, user } = storeToRefs(auth)
const router = useRouter()
const route = useRoute()

const REPORT_TIERS = ['pro', 'investor', 'enterprise']
const hasReportAccess = computed(() => REPORT_TIERS.includes(user.value?.tier ?? 'free'))

const report = ref<ParcelReportResult | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let requestToken = 0

const CONFIDENCE_COLOR: Record<string, string> = {
  high: 'positive',
  medium: 'amber-7',
  low: 'grey-6',
}

function goLogin(): void {
  void router.push({ name: 'login', query: { redirect: route.fullPath } })
}

watch(
  () => props.parcelNumber,
  () => {
    requestToken++
    report.value = null
    error.value = null
    loading.value = false
  },
)

async function draft(): Promise<void> {
  const token = ++requestToken
  loading.value = true
  error.value = null
  try {
    const result = await api.getParcelReport(props.parcelNumber)
    if (token !== requestToken) return
    report.value = result
  } catch (cause) {
    if (token !== requestToken) return
    report.value = null
    if (cause instanceof ApiError && cause.status === 401) {
      auth.logout()
      goLogin()
      error.value = 'Your session expired — please sign in again.'
    } else {
      error.value = cause instanceof ApiError ? cause.message : 'Failed to draft the report.'
    }
  } finally {
    if (token === requestToken) loading.value = false
  }
}
</script>

<template>
  <q-card flat bordered class="rounded-borders">
    <q-card-section class="q-pb-sm">
      <div class="row items-center q-mb-sm">
        <q-icon name="description" size="20px" class="q-mr-sm text-primary" />
        <div class="text-subtitle1">Investment report</div>
        <q-space />
        <q-chip
          v-if="report"
          dense
          square
          :color="CONFIDENCE_COLOR[report.confidence]"
          text-color="white"
          class="text-caption"
        >
          {{ report.confidence }} confidence
        </q-chip>
      </div>

      <div v-if="!isAuthenticated" class="signin-gate column items-center q-py-md">
        <q-icon name="lock" size="28px" color="grey-5" />
        <div class="text-body2 text-grey-7 text-center q-my-sm">
          Sign in to draft an AI investment memo for this parcel.
        </div>
        <q-btn unelevated no-caps color="primary" icon="login" label="Sign in" @click="goLogin" />
      </div>

      <div v-else-if="!hasReportAccess" class="upgrade-gate column items-center q-py-md">
        <q-icon name="auto_awesome" size="28px" color="grey-5" />
        <div class="text-body2 text-grey-7 text-center q-my-sm">
          The AI investment report is a Pro feature — a full memo synthesizing buildability,
          valuation, deal math, and risks for this parcel.
        </div>
        <q-btn
          unelevated
          no-caps
          color="primary"
          icon="bolt"
          label="Upgrade to Pro"
          :to="{ name: 'account' }"
        />
      </div>

      <template v-else>
        <div v-if="!report && !loading" class="column items-start">
          <div class="text-body2 text-grey-7 q-mb-sm">
            Draft a multi-section memo — buildability, valuation, deal math, and risks —
            synthesized from this parcel's computed analysis.
          </div>
          <q-btn
            unelevated
            no-caps
            color="primary"
            icon="auto_awesome"
            label="Draft report"
            @click="draft"
          />
        </div>

        <div v-if="loading" class="row items-center q-py-md text-grey-7">
          <q-spinner-dots size="24px" class="q-mr-sm" /> Drafting the report…
        </div>

        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mt-sm">
          {{ error }}
        </q-banner>

        <div v-if="report && !loading" class="report">
          <div class="report-headline">{{ report.headline }}</div>
          <div v-for="section in report.sections" :key="section.heading" class="report-section">
            <div class="report-heading">{{ section.heading }}</div>
            <div class="report-body">{{ section.body }}</div>
          </div>
          <div class="report-reco">
            <div class="report-heading">Recommendation</div>
            <div class="report-body">{{ report.recommendation }}</div>
          </div>
          <div class="report-note">
            AI-generated from LotScope's computed data · informational, not legal or financial
            advice.
          </div>
          <q-btn
            flat
            dense
            no-caps
            size="sm"
            color="grey-7"
            icon="refresh"
            label="Redraft"
            class="q-mt-sm"
            @click="draft"
          />
        </div>
      </template>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.report-headline {
  font-size: 15px;
  font-weight: 700;
  color: var(--lot-ink);
  line-height: 1.35;
  margin-bottom: 12px;
}
.report-section,
.report-reco {
  margin-bottom: 10px;
}
.report-heading {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--lot-muted);
  margin-bottom: 2px;
}
.report-body {
  font-size: 13px;
  line-height: 1.5;
  color: var(--lot-ink);
}
.report-reco {
  border-left: 3px solid var(--lot-accent, #6366f1);
  padding-left: 10px;
}
.report-note {
  margin-top: 10px;
  font-size: 11px;
  color: var(--lot-faint);
  line-height: 1.4;
}
.signin-gate,
.upgrade-gate {
  text-align: center;
}
</style>
