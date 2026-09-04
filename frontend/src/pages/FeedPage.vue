<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import { severityColor, severityIcon } from '@/lib/format'
import type { FeedEvent, FeedResponse } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useSavedSearchesStore } from '@/stores/savedSearches'

const router = useRouter()
const auth = useAuthStore()
const savedSearches = useSavedSearchesStore()
const { user } = storeToRefs(auth)
const { searches } = storeToRefs(savedSearches)

const FEED_TIERS = ['pro', 'investor', 'enterprise']
const hasAccess = computed(() => FEED_TIERS.includes(user.value?.tier ?? 'free'))

const WINDOW_OPTIONS = [
  { label: 'Last 24 hours', value: 1 },
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 },
]

const days = ref(1)
const savedSearchId = ref<number | null>(null)
const feed = ref<FeedResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const searchOptions = computed(() => [
  { label: 'All of Philadelphia', value: null },
  ...searches.value.map((s) => ({ label: s.name, value: s.id })),
])

async function load(): Promise<void> {
  if (!hasAccess.value) return
  loading.value = true
  error.value = null
  try {
    feed.value = await api.getFeed({
      days: days.value,
      savedSearchId: savedSearchId.value ?? undefined,
      limit: 200,
    })
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load the feed.'
  } finally {
    loading.value = false
  }
}

function openEvent(event: FeedEvent): void {
  void router.push({ name: 'parcel', params: { id: event.parcel_number } })
}

function whenLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

onMounted(() => {
  if (hasAccess.value) {
    void savedSearches.ensureLoaded()
    void load()
  }
})
watch([days, savedSearchId], load)
</script>

<template>
  <q-page class="q-pa-md">
    <div class="feed-wrap">
      <div v-if="!hasAccess" class="upgrade">
        <q-icon name="bolt" size="52px" color="grey-4" />
        <div class="text-h6 q-mt-md">The Deal Feed is a Pro feature</div>
        <div class="text-body2 text-grey-7 q-mb-md">
          See every change across the city — new delinquencies, sheriff sales, dangerous buildings,
          permits — filtered to your buy box.
        </div>
        <q-btn unelevated no-caps color="primary" label="Upgrade" :to="{ name: 'account' }" />
      </div>

      <template v-else>
        <div class="row items-end q-col-gutter-md q-mb-md">
          <div class="col-auto">
            <div class="text-caption text-grey-7 q-mb-xs">Window</div>
            <q-select
              v-model="days"
              outlined
              dense
              emit-value
              map-options
              :options="WINDOW_OPTIONS"
              style="min-width: 160px"
            />
          </div>
          <div class="col-auto">
            <div class="text-caption text-grey-7 q-mb-xs">Filter</div>
            <q-select
              v-model="savedSearchId"
              outlined
              dense
              emit-value
              map-options
              :options="searchOptions"
              style="min-width: 200px"
            />
          </div>
        </div>

        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
          {{ error }}
        </q-banner>

        <div v-if="feed && feed.summary.length" class="summary q-mb-md">
          <q-chip
            v-for="item in feed.summary"
            :key="item.code"
            square
            color="grey-2"
            text-color="grey-9"
          >
            <b class="q-mr-xs">{{ item.count }}</b> {{ item.label }}
          </q-chip>
        </div>

        <q-inner-loading :showing="loading" color="primary" />

        <q-list v-if="feed && feed.events.length" bordered separator class="rounded-borders">
          <q-item
            v-for="event in feed.events"
            :key="`${event.parcel_number}-${event.code}-${event.detected_at}`"
            v-ripple
            clickable
            @click="openEvent(event)"
          >
            <q-item-section avatar>
              <q-icon :name="severityIcon(event.severity)" :color="severityColor(event.severity)" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ event.label }}</q-item-label>
              <q-item-label caption class="ellipsis">
                {{ event.address ?? event.parcel_number }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-badge v-if="event.opportunity_score !== null" color="primary" outline>
                {{ event.opportunity_score }}
              </q-badge>
              <div class="text-caption text-grey-6 q-mt-xs">{{ whenLabel(event.detected_at) }}</div>
            </q-item-section>
          </q-item>
        </q-list>

        <div v-else-if="feed && !loading" class="empty">
          <q-icon name="check_circle" size="40px" color="positive" />
          <div class="text-body1 q-mt-sm">No changes in this window.</div>
          <div class="text-caption text-grey-6">
            Widen the window or adjust your saved-search filter.
          </div>
        </div>

        <div v-if="feed && feed.returned < feed.total" class="text-caption text-grey-6 q-mt-sm">
          Showing the {{ feed.returned }} most recent of {{ feed.total }} changes.
        </div>
      </template>
    </div>
  </q-page>
</template>

<style scoped>
.feed-wrap {
  max-width: 860px;
  margin: 0 auto;
  position: relative;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.upgrade,
.empty {
  text-align: center;
  padding: 56px 20px;
}
</style>
