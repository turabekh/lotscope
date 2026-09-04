<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import OutreachMailerDialog, { type MailerFields } from '@/components/OutreachMailerDialog.vue'
import UpgradePrompt from '@/components/UpgradePrompt.vue'
import { ApiError, api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { SavedSearchItem, SavedSearchMatchItem, SearchCriteria } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { emptyCriteria, useSavedSearchesStore } from '@/stores/savedSearches'

const ZONING_PRESETS = ['RSA5', 'RSA3', 'RM1', 'RM2', 'CMX1', 'CMX2', 'CMX2.5', 'CMX3', 'ICMX']

const route = useRoute()
const router = useRouter()
const $q = useQuasar()
const store = useSavedSearchesStore()
const auth = useAuthStore()
const { searches, limit, used, atLimit, loading } = storeToRefs(store)

const isFree = computed(() => (auth.user?.tier ?? 'free') === 'free')
const exportingId = ref<number | null>(null)

const mailerSearchId = ref<number | null>(null)
const generatingLetters = ref(false)
const mailerError = ref<string | null>(null)
const mailerOpen = computed({
  get: () => mailerSearchId.value !== null,
  set: (value: boolean) => {
    if (!value) mailerSearchId.value = null
  },
})

async function generateLetters(fields: MailerFields): Promise<void> {
  if (mailerSearchId.value === null) return
  generatingLetters.value = true
  mailerError.value = null
  try {
    await api.generateSavedSearchLetters(mailerSearchId.value, {
      fromName: fields.fromName,
      fromContact: fields.fromContact,
      message: fields.message || undefined,
      onePerOwner: fields.onePerOwner,
    })
    mailerSearchId.value = null
  } catch (cause) {
    mailerError.value = cause instanceof ApiError ? cause.message : 'Could not generate letters.'
  } finally {
    generatingLetters.value = false
  }
}

const showForm = ref(false)
const saving = ref(false)
const name = ref('')
const alertsEnabled = ref(true)
const criteria = reactive<SearchCriteria>(emptyCriteria())

const matches = reactive<Record<number, SavedSearchMatchItem[]>>({})
const expandedId = ref<number | null>(null)
const loadingMatches = ref(false)

onMounted(async () => {
  await store.load()
  if (route.query.vacant === '1') {
    criteria.vacant_only = true
    showForm.value = true
  }
})

function resetForm(): void {
  name.value = ''
  alertsEnabled.value = true
  Object.assign(criteria, emptyCriteria())
}

async function submit(): Promise<void> {
  if (name.value.trim().length === 0) return
  saving.value = true
  try {
    await store.create({
      name: name.value.trim(),
      criteria: { ...criteria },
      alerts_enabled: alertsEnabled.value,
    })
    resetForm()
    showForm.value = false
    $q.notify({ type: 'positive', message: 'Saved search created.' })
  } catch (error) {
    const message =
      error instanceof ApiError && error.status === 429
        ? 'You have reached your plan limit for saved searches.'
        : 'Could not create the saved search.'
    $q.notify({ type: 'negative', message })
  } finally {
    saving.value = false
  }
}

async function toggle(search: SavedSearchItem): Promise<void> {
  if (expandedId.value === search.id) {
    expandedId.value = null
    return
  }
  expandedId.value = search.id
  if (matches[search.id] === undefined) {
    loadingMatches.value = true
    try {
      const detail = await api.getSavedSearch(search.id)
      matches[search.id] = detail.matches
    } finally {
      loadingMatches.value = false
    }
  }
}

async function runNow(search: SavedSearchItem): Promise<void> {
  const detail = await store.run(search.id)
  matches[search.id] = detail.matches
  expandedId.value = search.id
  $q.notify({
    type: detail.new_count > 0 ? 'positive' : 'info',
    message:
      detail.new_count > 0
        ? `${detail.new_count} new lot(s) found.`
        : 'No new lots since the last check.',
  })
}

async function toggleAlerts(search: SavedSearchItem): Promise<void> {
  await store.setAlerts(search.id, !search.alerts_enabled)
}

async function exportCsv(search: SavedSearchItem): Promise<void> {
  exportingId.value = search.id
  try {
    await api.exportSavedSearch(search.id)
  } catch (cause) {
    $q.notify({
      type: 'negative',
      message: cause instanceof ApiError ? cause.message : 'Could not export this search.',
    })
  } finally {
    exportingId.value = null
  }
}

function remove(search: SavedSearchItem): void {
  void store.remove(search.id)
  delete matches[search.id]
}

function openParcel(match: SavedSearchMatchItem): void {
  void router.push({ name: 'parcel', params: { id: match.parcel_number } })
}

function summarize(search: SavedSearchItem): string {
  const c = search.criteria
  const parts: string[] = []
  if (c.vacant_only) parts.push('Vacant')
  if (c.zoning_codes.length) parts.push(c.zoning_codes.join('/'))
  if (c.zip_code) parts.push(`ZIP ${c.zip_code}`)
  if (c.min_market_value != null || c.max_market_value != null) {
    parts.push(
      `Value ${formatCurrency(c.min_market_value ?? 0)}–${
        c.max_market_value != null ? formatCurrency(c.max_market_value) : '∞'
      }`,
    )
  }
  if (c.min_lot_area_sqft != null) parts.push(`≥${c.min_lot_area_sqft} sqft`)
  if (c.min_opportunity_score != null) parts.push(`Opp ≥${c.min_opportunity_score}`)
  if (c.min_distress_score != null) parts.push(`Distress ≥${c.min_distress_score}`)
  if (c.is_delinquent) parts.push('Delinquent')
  if (c.in_sheriff_sale) parts.push('Sheriff sale')
  return parts.length ? parts.join(' · ') : 'All parcels'
}

function asNumber(value: string | number | null): number | null {
  if (value === null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
</script>

<template>
  <div class="ss-wrap">
    <div class="text-caption text-grey-7 q-mb-sm row items-center">
      <q-icon name="saved_search" size="16px" class="q-mr-xs" />
      {{ used }} saved search<span v-if="used !== 1">es</span
      ><span v-if="limit !== null">&nbsp;of {{ limit }}</span
      >. New lots are alerted by email.
      <q-space />
      <q-btn
        v-if="!showForm"
        unelevated
        dense
        no-caps
        size="sm"
        color="primary"
        icon="add"
        label="New search"
        :disable="atLimit"
        @click="showForm = true"
      />
    </div>

    <UpgradePrompt
      v-if="atLimit && !showForm"
      cap="saved_search"
      variant="banner"
      class="q-mb-sm"
    />

    <q-card v-if="showForm" flat bordered class="q-pa-md q-mb-md">
      <div class="text-subtitle2 q-mb-sm">New saved search</div>
      <q-input v-model="name" outlined dense label="Name" autofocus class="q-mb-sm" />

      <div class="row q-col-gutter-sm">
        <div class="col-12">
          <q-select
            v-model="criteria.zoning_codes"
            :options="ZONING_PRESETS"
            outlined
            dense
            multiple
            use-chips
            use-input
            hide-dropdown-icon
            new-value-mode="add-unique"
            label="Zoning codes (e.g. RSA5)"
          />
        </div>
        <div class="col-6 col-sm-3">
          <q-input v-model="criteria.zip_code" outlined dense label="ZIP" maxlength="10" />
        </div>
        <div class="col-6 col-sm-3">
          <q-input
            :model-value="criteria.min_market_value"
            type="number"
            outlined
            dense
            label="Min value $"
            @update:model-value="(v) => (criteria.min_market_value = asNumber(v))"
          />
        </div>
        <div class="col-6 col-sm-3">
          <q-input
            :model-value="criteria.max_market_value"
            type="number"
            outlined
            dense
            label="Max value $"
            @update:model-value="(v) => (criteria.max_market_value = asNumber(v))"
          />
        </div>
        <div class="col-6 col-sm-3">
          <q-input
            :model-value="criteria.min_lot_area_sqft"
            type="number"
            outlined
            dense
            label="Min lot sqft"
            @update:model-value="(v) => (criteria.min_lot_area_sqft = asNumber(v))"
          />
        </div>
        <div class="col-6 col-sm-3">
          <q-input
            :model-value="criteria.min_opportunity_score"
            type="number"
            outlined
            dense
            label="Min opportunity"
            @update:model-value="(v) => (criteria.min_opportunity_score = asNumber(v))"
          />
        </div>
        <div class="col-6 col-sm-3">
          <q-input
            :model-value="criteria.min_distress_score"
            type="number"
            outlined
            dense
            label="Min distress"
            @update:model-value="(v) => (criteria.min_distress_score = asNumber(v))"
          />
        </div>
      </div>

      <div class="row items-center q-gutter-md q-mt-xs">
        <q-toggle v-model="criteria.vacant_only" dense label="Vacant only" color="amber-8" />
        <q-toggle
          :model-value="criteria.is_delinquent === true"
          dense
          label="Tax-delinquent"
          color="negative"
          @update:model-value="(v: boolean) => (criteria.is_delinquent = v ? true : null)"
        />
        <q-toggle
          :model-value="criteria.in_sheriff_sale === true"
          dense
          label="Sheriff sale"
          color="negative"
          @update:model-value="(v: boolean) => (criteria.in_sheriff_sale = v ? true : null)"
        />
        <q-toggle v-model="alertsEnabled" dense label="Email alerts" color="primary" />
      </div>

      <div class="row justify-end q-gutter-sm q-mt-sm">
        <q-btn flat dense no-caps color="grey-7" label="Cancel" @click="showForm = false" />
        <q-btn
          unelevated
          dense
          no-caps
          color="primary"
          label="Create"
          :loading="saving"
          :disable="name.trim().length === 0"
          @click="submit"
        />
      </div>
    </q-card>

    <q-inner-loading :showing="loading" color="primary" />

    <div v-if="!loading && searches.length === 0" class="empty">
      <q-icon name="saved_search" size="48px" color="grey-4" />
      <div class="text-subtitle1 text-grey-7 q-mt-sm">No saved searches yet</div>
      <div class="text-body2 text-grey-6">
        Save a set of criteria and get an email when new matching lots appear.
      </div>
    </div>

    <div class="ss-list">
      <q-card v-for="search in searches" :key="search.id" flat bordered class="lot-card q-pa-sm">
        <div class="ss-head" @click="toggle(search)">
          <div class="ss-title">
            <div class="ss-name ellipsis">
              {{ search.name }}
              <q-badge v-if="search.new_count > 0" color="negative" class="q-ml-xs">
                {{ search.new_count }} new
              </q-badge>
            </div>
            <div class="ss-meta ellipsis">{{ summarize(search) }}</div>
          </div>
          <q-chip dense square color="grey-2" text-color="grey-9" class="q-mr-xs">
            {{ search.match_count }} match<span v-if="search.match_count !== 1">es</span>
          </q-chip>
          <q-icon
            :name="expandedId === search.id ? 'expand_less' : 'expand_more'"
            size="20px"
            color="grey-6"
          />
        </div>

        <q-slide-transition>
          <div v-show="expandedId === search.id">
            <div class="row items-center q-gutter-sm q-mt-xs q-mb-sm">
              <q-toggle
                :model-value="search.alerts_enabled"
                dense
                size="sm"
                label="Email alerts"
                color="primary"
                @update:model-value="() => toggleAlerts(search)"
              />
              <q-btn
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                icon="refresh"
                label="Check now"
                @click="runNow(search)"
              />
              <q-btn
                v-if="isFree"
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                icon="lock"
                label="Export CSV"
                :to="{ name: 'account' }"
              >
                <q-tooltip>CSV export is a Pro feature — upgrade to download.</q-tooltip>
              </q-btn>
              <q-btn
                v-else
                flat
                dense
                no-caps
                size="sm"
                color="primary"
                icon="download"
                label="Export CSV"
                :loading="exportingId === search.id"
                @click="exportCsv(search)"
              />
              <q-btn
                v-if="isFree"
                flat
                dense
                no-caps
                size="sm"
                color="deep-purple-6"
                icon="lock"
                label="Mail letters"
                :to="{ name: 'account' }"
              >
                <q-tooltip>Direct-mail letters are a Pro feature — upgrade to generate.</q-tooltip>
              </q-btn>
              <q-btn
                v-else
                flat
                dense
                no-caps
                size="sm"
                color="deep-purple-6"
                icon="mail"
                label="Mail letters"
                @click="mailerSearchId = search.id"
              />
              <q-space />
              <q-btn
                flat
                dense
                round
                size="sm"
                icon="delete_outline"
                color="grey-6"
                aria-label="Delete"
                @click="remove(search)"
              />
            </div>

            <q-inner-loading :showing="loadingMatches" color="primary" />
            <q-list v-if="matches[search.id]" dense bordered class="rounded-borders">
              <q-item
                v-for="match in matches[search.id]"
                :key="match.parcel_number"
                clickable
                @click="openParcel(match)"
              >
                <q-item-section>
                  <q-item-label class="ellipsis">
                    {{ match.address ?? match.parcel_number }}
                    <q-badge v-if="match.is_new" color="negative" class="q-ml-xs">new</q-badge>
                  </q-item-label>
                  <q-item-label caption>
                    {{ match.base_zoning_code ?? '—' }}
                    <span v-if="match.market_value">
                      · {{ formatCurrency(match.market_value) }}</span
                    >
                  </q-item-label>
                </q-item-section>
                <q-item-section v-if="match.opportunity_score !== null" side>
                  <q-badge color="primary" outline>{{ match.opportunity_score }}</q-badge>
                </q-item-section>
              </q-item>
              <q-item v-if="matches[search.id]!.length === 0">
                <q-item-section class="text-grey-6">No matching lots right now.</q-item-section>
              </q-item>
            </q-list>
          </div>
        </q-slide-transition>
      </q-card>
    </div>

    <OutreachMailerDialog
      v-model="mailerOpen"
      subtitle="One personalized purchase-interest letter per owner matching this saved search."
      :submitting="generatingLetters"
      :error-message="mailerError"
      @submit="generateLetters"
    />
  </div>
</template>

<style scoped>
.ss-wrap {
  max-width: 760px;
  margin: 0 auto;
  position: relative;
}
.ss-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ss-head {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 8px;
}
.ss-title {
  flex: 1;
  min-width: 0;
}
.ss-name {
  font-weight: 600;
  color: var(--lot-ink);
}
.ss-meta {
  font-size: 12px;
  color: var(--lot-muted);
}
.empty {
  text-align: center;
  padding: 48px 16px;
}
</style>
