<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import FirstSteps from '@/components/FirstSteps.vue'
import NextAction from '@/components/NextAction.vue'
import { api } from '@/lib/api'
import { formatCurrency, formatNumber, scoreColor } from '@/lib/format'
import type { LeadItem } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { STAGES, usePipelineStore } from '@/stores/pipeline'
import { useSavedSearchesStore } from '@/stores/savedSearches'
import { useWatchlistStore } from '@/stores/watchlist'

const LEADS_PREVIEW = 5

const router = useRouter()
const auth = useAuthStore()
const watchlist = useWatchlistStore()
const savedSearches = useSavedSearchesStore()
const pipeline = usePipelineStore()

const { user } = storeToRefs(auth)
const { items: watchItems, alerts, used: watchUsed } = storeToRefs(watchlist)
const { searches, newTotal, used: searchUsed } = storeToRefs(savedSearches)
const { deals, used: dealsUsed } = storeToRefs(pipeline)

const marketLabel = 'Philadelphia'
const greetingName = computed(() => user.value?.full_name?.split(' ')[0] ?? null)

interface ChangeRow {
  key: string
  kind: 'watchlist' | 'search'
  title: string
  detail: string
  severity: 'high' | 'medium' | 'info'
  direction: 'up' | 'down' | 'none'
  meaning: 'better' | 'worse' | 'neutral'
  to: () => void
}

const RISING_IS_BETTER: Record<string, boolean> = { distress: true, opportunity: true }

function changeMeaning(code: string, direction: 'up' | 'down' | 'none'): ChangeRow['meaning'] {
  if (direction === 'none') return 'neutral'
  const risingIsBetter = RISING_IS_BETTER[code]
  if (risingIsBetter === undefined) return 'neutral'
  const rising = direction === 'up'
  return rising === risingIsBetter ? 'better' : 'worse'
}

const changeRows = computed<ChangeRow[]>(() => {
  const rows: ChangeRow[] = []
  for (const item of watchItems.value) {
    if (!item.has_alerts) continue
    for (const change of item.changes) {
      rows.push({
        key: `w:${item.parcel_number}:${change.code}`,
        kind: 'watchlist',
        title: item.address ?? item.parcel_number,
        detail: change.label,
        severity: change.severity,
        direction: change.direction ?? 'none',
        meaning: changeMeaning(change.code, change.direction ?? 'none'),
        to: () => openParcel(item.parcel_number),
      })
    }
  }
  for (const search of searches.value) {
    if (search.new_count <= 0) continue
    rows.push({
      key: `s:${search.id}`,
      kind: 'search',
      title: search.name,
      detail: `${search.new_count} new ${search.new_count === 1 ? 'match' : 'matches'}`,
      severity: 'info',
      direction: 'none',
      meaning: 'neutral',
      to: () =>
        void router.push({
          name: 'lists',
          query: { tab: 'searches' },
        }),
    })
  }
  return rows.slice(0, 8)
})

const pipelineValue = computed(() =>
  deals.value.reduce((sum, deal) => sum + (deal.target_price ?? deal.market_value ?? 0), 0),
)

const stageCounts = computed(() =>
  STAGES.map((stage) => ({
    ...stage,
    count: deals.value.filter((deal) => deal.stage === stage.value).length,
  })).filter((stage) => stage.count > 0),
)

const leads = ref<LeadItem[]>([])
const leadsLoading = ref(true)

function openParcel(parcelNumber: string): void {
  void router.push({ name: 'parcel', params: { id: parcelNumber } })
}

function severityColor(severity: 'high' | 'medium' | 'info'): string {
  if (severity === 'high') return 'negative'
  if (severity === 'medium') return 'amber-8'
  return 'primary'
}

const needsBuyBox = ref(false)

async function refreshBuyBoxState(): Promise<void> {
  try {
    const matches = await api.getBuyBoxMatches(1)
    needsBuyBox.value = !matches.has_profile || matches.criteria_applied.length === 0
  } catch {
    needsBuyBox.value = false
  }
}

onMounted(async () => {
  void refreshBuyBoxState()
  void watchlist.ensureLoaded()
  void savedSearches.ensureLoaded()
  void pipeline.ensureLoaded()
  try {
    const response = await api.getLeads({})
    leads.value = response.leads.slice(0, LEADS_PREVIEW)
  } finally {
    leadsLoading.value = false
  }
})
</script>

<template>
  <q-page class="q-pa-md">
    <div class="home-wrap">
      <header class="home-head q-mb-md">
        <div class="text-h5 text-weight-bold">
          {{ greetingName ? `Welcome back, ${greetingName}` : 'Welcome back' }}
        </div>
        <div class="text-body2 text-grey-7">Your {{ marketLabel }} snapshot</div>
      </header>

      <NextAction v-if="!needsBuyBox" :top-lead="leads[0] ?? null" class="q-mb-md" />
      <q-banner v-else dense class="q-mb-md bg-blue-1" data-test="buy-box-prompt">
        <template #avatar><q-icon name="tune" color="primary" /></template>
        Set your buy box and every lot gets screened against your numbers.
        <template #action>
          <q-btn flat no-caps color="primary" label="Set it up" :to="{ name: 'account' }" />
        </template>
      </q-banner>
      <FirstSteps class="q-mb-md" />

      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-7">
          <q-card flat bordered class="lot-card home-card">
            <div class="card-head">
              <div class="card-title">
                <q-icon name="notifications_active" size="19px" />
                What changed
              </div>
              <q-badge v-if="alerts + newTotal > 0" color="negative" rounded>
                {{ alerts + newTotal }}
              </q-badge>
            </div>
            <q-separator />
            <q-list v-if="changeRows.length" separator>
              <q-item v-for="row in changeRows" :key="row.key" v-ripple clickable @click="row.to()">
                <q-item-section avatar>
                  <q-icon
                    :name="row.kind === 'search' ? 'saved_search' : 'bookmark'"
                    :color="severityColor(row.severity)"
                  />
                </q-item-section>
                <q-item-section>
                  <q-item-label class="ellipsis">{{ row.title }}</q-item-label>
                  <q-item-label caption class="change-detail">
                    <q-icon
                      v-if="row.direction !== 'none'"
                      :name="row.direction === 'up' ? 'arrow_upward' : 'arrow_downward'"
                      size="13px"
                      :class="`meaning-${row.meaning}`"
                    />
                    <span :class="`meaning-${row.meaning}`">{{ row.detail }}</span>
                  </q-item-label>
                </q-item-section>
                <q-item-section side><q-icon name="chevron_right" color="grey-5" /></q-item-section>
              </q-item>
            </q-list>
            <div v-else class="empty-slot">
              <q-icon name="check_circle" size="30px" color="positive" />
              <div class="text-body2 text-grey-7 q-mt-sm">You're all caught up.</div>
              <q-btn
                flat
                dense
                no-caps
                color="primary"
                label="Find new lots"
                :to="{ name: 'explore' }"
              />
            </div>
          </q-card>
        </div>

        <div class="col-12 col-md-5">
          <q-card flat bordered class="lot-card home-card">
            <div class="card-head">
              <div class="card-title"><q-icon name="view_kanban" size="19px" />Pipeline</div>
              <q-btn
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                label="Open"
                :to="{ name: 'pipeline' }"
              />
            </div>
            <q-separator />
            <template v-if="dealsUsed > 0">
              <div class="pipeline-value">
                <div class="text-caption text-grey-7">Total pipeline value</div>
                <div class="text-h6 text-weight-bold">{{ formatCurrency(pipelineValue) }}</div>
              </div>
              <div class="stage-rows">
                <div v-for="stage in stageCounts" :key="stage.value" class="stage-row">
                  <q-badge :color="stage.color" rounded class="stage-dot" />
                  <span class="stage-label">{{ stage.label }}</span>
                  <span class="stage-count">{{ stage.count }}</span>
                </div>
              </div>
            </template>
            <div v-else class="empty-slot">
              <q-icon name="view_kanban" size="30px" color="grey-4" />
              <div class="text-body2 text-grey-7 q-mt-sm">No deals yet.</div>
              <q-btn
                flat
                dense
                no-caps
                color="primary"
                label="Browse leads"
                :to="{ name: 'leads' }"
              />
            </div>
          </q-card>
        </div>

        <div class="col-12 col-md-7">
          <q-card flat bordered class="lot-card home-card">
            <div class="card-head">
              <div class="card-title"><q-icon name="sell" size="19px" />Top leads</div>
              <q-btn
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                label="See all"
                :to="{ name: 'leads' }"
              />
            </div>
            <q-separator />
            <q-inner-loading :showing="leadsLoading" color="primary" />
            <q-list v-if="leads.length" separator>
              <q-item
                v-for="lead in leads"
                :key="lead.parcel_number"
                v-ripple
                clickable
                @click="openParcel(lead.parcel_number)"
              >
                <q-item-section>
                  <q-item-label class="ellipsis">{{
                    lead.address ?? lead.parcel_number
                  }}</q-item-label>
                  <q-item-label caption class="ellipsis">
                    {{ lead.top_factors[0] ?? lead.base_zoning_code ?? '—' }}
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-badge :color="scoreColor(lead.score)" rounded>{{
                    formatNumber(lead.score)
                  }}</q-badge>
                </q-item-section>
              </q-item>
            </q-list>
            <div v-else-if="!leadsLoading" class="empty-slot">
              <q-icon name="sell" size="30px" color="grey-4" />
              <div class="text-body2 text-grey-7 q-mt-sm">No leads match right now.</div>
              <q-btn
                flat
                dense
                no-caps
                color="primary"
                label="Explore the map"
                :to="{ name: 'explore' }"
              />
            </div>
          </q-card>
        </div>

        <div class="col-12 col-md-5">
          <q-card flat bordered class="lot-card home-card">
            <div class="card-head">
              <div class="card-title"><q-icon name="dataset" size="19px" />{{ marketLabel }}</div>
            </div>
            <q-separator />
            <div class="stat-grid">
              <router-link class="stat" :to="{ name: 'lists', query: { tab: 'lots' } }">
                <div class="stat-num">{{ watchUsed }}</div>
                <div class="stat-label">Watchlist</div>
              </router-link>
              <router-link
                class="stat"
                :to="{
                  name: 'lists',
                  query: { tab: 'searches' },
                }"
              >
                <div class="stat-num">{{ searchUsed }}</div>
                <div class="stat-label">Saved searches</div>
              </router-link>
              <router-link class="stat" :to="{ name: 'pipeline' }">
                <div class="stat-num">{{ dealsUsed }}</div>
                <div class="stat-label">Deals</div>
              </router-link>
            </div>
            <q-separator />
            <div class="coverage-note">
              Zoning, sales, and L&amp;I from {{ marketLabel }} open data, provided as-is.
            </div>
          </q-card>
        </div>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.change-detail {
  display: flex;
  align-items: center;
  gap: 3px;
}
.meaning-better {
  color: var(--lot-score-positive, #15803d);
}
.meaning-worse {
  color: var(--lot-sev-high, #b91c1c);
}

.home-wrap {
  max-width: 1080px;
  margin: 0 auto;
}
.home-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: var(--lot-ink);
}
.empty-slot {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px 16px;
  gap: 4px;
}
.pipeline-value {
  padding: 14px 16px 8px;
}
.stage-rows {
  padding: 0 16px 12px;
}
.stage-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
}
.stage-dot {
  width: 9px;
  height: 9px;
  padding: 0;
  min-height: 0;
}
.stage-label {
  color: var(--lot-muted);
  font-weight: 500;
}
.stage-count {
  margin-left: auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--lot-ink);
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}
.stat {
  padding: 16px 8px;
  text-align: center;
  text-decoration: none;
  border-right: 1px solid var(--lot-border);
  transition: background 0.15s ease;
}
.stat:last-child {
  border-right: none;
}
.stat:hover {
  background: var(--lot-surface-2);
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--lot-ink);
  font-variant-numeric: tabular-nums;
}
.stat-label {
  font-size: 12px;
  color: var(--lot-muted);
}
.coverage-note {
  padding: 12px 14px;
  font-size: 12px;
  color: var(--lot-muted);
}
</style>
