<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { LeadItem } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useMarketStore } from '@/stores/market'

const router = useRouter()
const market = useMarketStore()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const leads = ref<LeadItem[]>([])
const limit = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)

const minScore = ref(30)
const vacantOnly = ref(false)
const zipCode = ref('')

const SCORE_OPTIONS = [
  { label: 'Any distress (30+)', value: 30 },
  { label: 'Notable (50+)', value: 50 },
  { label: 'Severe (70+)', value: 70 },
]

function scoreColor(score: number): string {
  if (score >= 60) return 'negative'
  if (score >= 30) return 'warning'
  return 'blue-grey-6'
}

function money(value: number | null): string {
  if (value == null) return '—'
  const sign = value < 0 ? '-' : ''
  return `${sign}$${Math.abs(Math.round(value)).toLocaleString('en-US')}`
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const response = await api.getLeads({
      minScore: minScore.value,
      vacantOnly: vacantOnly.value,
      zipCode: zipCode.value.trim() || undefined,
    })
    leads.value = response.leads
    limit.value = response.limit
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load leads.'
  } finally {
    loading.value = false
  }
}

function openLead(lead: LeadItem): void {
  void router.push({ name: 'parcel', params: { market: market.active, id: lead.parcel_number } })
}

onMounted(load)
</script>

<template>
  <q-page class="q-pa-md">
    <div class="leads-wrap">
      <q-card flat bordered class="lot-card q-pa-md q-mb-md">
        <div class="row q-col-gutter-md items-end">
          <div class="col-12 col-sm-4">
            <div class="text-caption text-grey-7 q-mb-xs">Distress level</div>
            <q-select
              v-model="minScore"
              outlined
              dense
              emit-value
              map-options
              :options="SCORE_OPTIONS"
            />
          </div>
          <div class="col-6 col-sm-3">
            <div class="text-caption text-grey-7 q-mb-xs">ZIP code</div>
            <q-input v-model="zipCode" outlined dense placeholder="e.g. 19140" maxlength="10" />
          </div>
          <div class="col-6 col-sm-3">
            <q-toggle v-model="vacantOnly" label="Vacant only" dense color="amber-8" />
          </div>
          <div class="col-12 col-sm-2">
            <q-btn
              class="full-width"
              unelevated
              color="primary"
              no-caps
              icon="search"
              label="Find"
              :loading="loading"
              @click="load"
            />
          </div>
        </div>
      </q-card>

      <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
        {{ error }}
      </q-banner>

      <div v-if="user" class="text-caption text-grey-7 q-mb-sm row items-center">
        <q-icon name="workspace_premium" size="16px" class="q-mr-xs" />
        Showing the top {{ leads.length }} on your
        <b class="q-mx-xs text-capitalize">{{ user.tier }}</b> plan (max {{ limit }}).
        <template v-if="user.tier === 'free'">
          <q-btn
            flat
            dense
            no-caps
            size="sm"
            color="primary"
            label="Upgrade for more"
            :to="{ name: 'account' }"
            class="q-ml-xs"
          />
        </template>
      </div>

      <q-inner-loading :showing="loading" color="primary" />

      <div v-if="!loading && leads.length === 0 && !error" class="empty">
        <q-icon name="sentiment_satisfied" size="48px" color="grey-4" />
        <div class="text-subtitle1 text-grey-7 q-mt-sm">No leads match these filters</div>
        <div class="text-body2 text-grey-6">Try a lower distress level or a different ZIP.</div>
      </div>

      <div class="lead-list">
        <q-card
          v-for="(lead, index) in leads"
          :key="lead.parcel_number"
          flat
          bordered
          class="lead lot-card"
          @click="openLead(lead)"
        >
          <div class="lead-rank">{{ index + 1 }}</div>
          <q-circular-progress
            show-value
            :value="lead.score"
            :min="0"
            :max="100"
            size="46px"
            :thickness="0.22"
            :color="scoreColor(lead.score)"
            track-color="grey-3"
            class="q-mx-sm"
          >
            <span class="text-weight-bold">{{ lead.score }}</span>
          </q-circular-progress>
          <div class="lead-body">
            <div class="lead-addr ellipsis">{{ lead.address ?? lead.parcel_number }}</div>
            <div class="lead-owner ellipsis">{{ lead.owner ?? 'Owner unknown' }}</div>
            <div class="lead-tags">
              <q-badge
                v-for="tag in lead.top_factors"
                :key="tag"
                color="red-1"
                text-color="negative"
                class="lead-tag"
              >
                {{ tag }}
              </q-badge>
              <q-badge v-if="lead.base_zoning_code" color="grey-3" text-color="grey-9">
                {{ lead.base_zoning_code }}
              </q-badge>
              <q-badge
                v-if="lead.is_underpriced"
                color="green-1"
                text-color="green-9"
                class="lead-tag"
              >
                Underpriced · MAO {{ money(lead.max_allowable_offer) }}
              </q-badge>
              <q-badge
                v-else-if="lead.deal_score != null"
                color="blue-1"
                text-color="primary"
                class="lead-tag"
              >
                Deal {{ Math.round(lead.deal_score) }}
              </q-badge>
            </div>
          </div>
          <q-icon name="chevron_right" color="grey-5" size="22px" />
        </q-card>
      </div>

      <div class="text-caption text-grey-5 q-mt-md">
        Informational only — distress signals from public city data, not contact details or advice.
        Respect Fair Housing, TCPA, and CAN-SPAM rules in any outreach.
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.leads-wrap {
  max-width: 820px;
  margin: 0 auto;
  position: relative;
}
.lead-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lead {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  transition: box-shadow 0.12s ease;
}
.lead:hover {
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.12);
}
.lead-rank {
  width: 22px;
  text-align: center;
  font-weight: 700;
  color: var(--lot-faint);
}
.lead-body {
  flex: 1;
  min-width: 0;
}
.lead-addr {
  font-weight: 600;
  color: var(--lot-ink);
}
.lead-owner {
  font-size: 12px;
  color: var(--lot-muted);
}
.lead-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 4px;
}
.lead-tag {
  font-size: 10px;
}
.empty {
  text-align: center;
  padding: 48px 16px;
}
</style>
