<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { formatCurrency } from '@/lib/format'
import type { WatchlistItem } from '@/lib/types'
import { useMarketStore } from '@/stores/market'
import { useParcelStore } from '@/stores/parcel'
import { useWatchlistStore } from '@/stores/watchlist'

const router = useRouter()
const parcelStore = useParcelStore()
const market = useMarketStore()
const watchlist = useWatchlistStore()
const { items, limit, used, loading, alerts } = storeToRefs(watchlist)

onMounted(() => void watchlist.load())

function scoreColor(score: number | null): string {
  if (score == null) return 'grey-5'
  if (score >= 65) return 'positive'
  if (score >= 45) return 'amber-8'
  return 'negative'
}

function changeColor(severity: string): string {
  if (severity === 'high') return 'negative'
  if (severity === 'medium') return 'warning'
  return 'info'
}

function markSeen(item: WatchlistItem): void {
  void watchlist.markSeen(item.parcel_number)
}

function openParcel(item: WatchlistItem): void {
  void parcelStore.select(item.parcel_number)
  void router.push({ name: 'explore', params: { market: market.active } })
}

function onTags(item: WatchlistItem, tags: string[]): void {
  void watchlist.updateItem(item.parcel_number, { tags })
}

function onNote(item: WatchlistItem, note: string | null): void {
  void watchlist.updateItem(item.parcel_number, { note: note ?? '' })
}

function remove(item: WatchlistItem): void {
  void watchlist.remove(item.parcel_number)
}
</script>

<template>
  <q-page class="q-pa-md">
    <div class="wl-wrap">
      <div class="text-caption text-grey-7 q-mb-sm row items-center">
        <q-icon name="bookmark" size="16px" class="q-mr-xs" />
        {{ used }} saved<span v-if="limit !== null">&nbsp;of {{ limit }}</span
        >.
        <q-badge v-if="alerts > 0" color="negative" class="q-ml-sm">
          {{ alerts }} with updates
        </q-badge>
        <q-btn
          v-if="limit !== null && used >= limit"
          flat
          dense
          no-caps
          size="sm"
          color="primary"
          label="Upgrade for more"
          :to="{ name: 'account' }"
          class="q-ml-xs"
        />
      </div>

      <q-inner-loading :showing="loading" color="primary" />

      <div v-if="!loading && items.length === 0" class="empty">
        <q-icon name="bookmark_border" size="48px" color="grey-4" />
        <div class="text-subtitle1 text-grey-7 q-mt-sm">No saved parcels yet</div>
        <div class="text-body2 text-grey-6">Open any lot and tap the bookmark to save it here.</div>
        <q-btn
          class="q-mt-md"
          unelevated
          no-caps
          color="primary"
          label="Browse the map"
          :to="{ name: 'explore', params: { market: market.active } }"
        />
      </div>

      <div class="wl-list">
        <q-card v-for="item in items" :key="item.parcel_number" flat bordered class="wl lot-card">
          <div class="wl-head">
            <q-circular-progress
              v-if="item.opportunity_score !== null"
              show-value
              :value="item.opportunity_score"
              :min="0"
              :max="100"
              size="42px"
              :thickness="0.22"
              :color="scoreColor(item.opportunity_score)"
              track-color="grey-3"
              class="q-mr-sm"
            >
              <span class="text-weight-bold">{{ item.opportunity_score }}</span>
            </q-circular-progress>
            <div class="wl-title" @click="openParcel(item)">
              <div class="wl-addr ellipsis">{{ item.address ?? item.parcel_number }}</div>
              <div class="wl-meta">
                {{ item.base_zoning_code ?? 'No zoning' }}
                <span v-if="item.is_vacant" class="text-amber-9">· Vacant</span>
                <span v-if="item.market_value"> · {{ formatCurrency(item.market_value) }}</span>
              </div>
            </div>
            <q-btn
              flat
              dense
              round
              icon="delete_outline"
              color="grey-6"
              aria-label="Remove"
              @click="remove(item)"
            />
          </div>

          <div v-if="item.changes.length" class="wl-changes">
            <q-icon name="notifications_active" size="16px" color="negative" class="q-mr-xs" />
            <q-badge
              v-for="change in item.changes"
              :key="change.code"
              :color="changeColor(change.severity)"
              text-color="white"
              class="wl-change"
            >
              {{ change.label }}
            </q-badge>
            <q-btn
              flat
              dense
              no-caps
              size="sm"
              color="grey-7"
              icon="done"
              label="Mark seen"
              class="q-ml-auto"
              @click="markSeen(item)"
            />
          </div>

          <q-select
            :model-value="item.tags"
            use-input
            use-chips
            multiple
            hide-dropdown-icon
            input-debounce="0"
            new-value-mode="add-unique"
            outlined
            dense
            label="Tags"
            class="q-mt-sm"
            @update:model-value="(value: string[]) => onTags(item, value)"
          />
          <q-input
            :model-value="item.note"
            outlined
            dense
            autogrow
            type="textarea"
            label="Notes"
            class="q-mt-sm"
            @change="
              (value: string | number | null) => onNote(item, value == null ? null : String(value))
            "
          />
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.wl-wrap {
  max-width: 760px;
  margin: 0 auto;
  position: relative;
}
.wl-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wl {
  padding: 12px 14px;
}
.wl-head {
  display: flex;
  align-items: center;
}
.wl-changes {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: var(--lot-radius-sm);
  background: #fff7f5;
  border: 1px solid #ffd9cf;
}
.wl-change {
  font-size: 10.5px;
}
.wl-title {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.wl-addr {
  font-weight: 600;
  color: var(--lot-ink);
}
.wl-addr:hover {
  color: var(--q-primary);
}
.wl-meta {
  font-size: 12px;
  color: var(--lot-muted);
}
.empty {
  text-align: center;
  padding: 48px 16px;
}
</style>
