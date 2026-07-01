<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import { formatCurrency } from '@/lib/format'
import type { DealItem, DealStage } from '@/lib/types'
import { useMarketStore } from '@/stores/market'
import { useParcelStore } from '@/stores/parcel'
import { STAGES, usePipelineStore } from '@/stores/pipeline'

const router = useRouter()
const parcelStore = useParcelStore()
const market = useMarketStore()
const pipeline = usePipelineStore()
const { deals, loading } = storeToRefs(pipeline)

const dragging = ref<string | null>(null)
const dragOver = ref<DealStage | null>(null)

onMounted(() => void pipeline.load())

function dealsIn(stage: DealStage): DealItem[] {
  return deals.value.filter((deal) => deal.stage === stage)
}

function scoreColor(score: number | null): string {
  if (score == null) return 'grey-5'
  if (score >= 65) return 'positive'
  if (score >= 45) return 'amber-8'
  return 'negative'
}

function openParcel(deal: DealItem): void {
  void parcelStore.select(deal.parcel_number)
  void router.push({ name: 'explore', params: { market: market.active } })
}

function onDragStart(event: DragEvent, deal: DealItem): void {
  dragging.value = deal.parcel_number
  event.dataTransfer?.setData('text/plain', deal.parcel_number)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onDrop(event: DragEvent, stage: DealStage): void {
  event.preventDefault()
  const parcelNumber = event.dataTransfer?.getData('text/plain') || dragging.value
  dragging.value = null
  dragOver.value = null
  if (parcelNumber) void pipeline.moveStage(parcelNumber, stage)
}

function saveNote(deal: DealItem, value: string | null): void {
  void pipeline.updateDeal(deal.parcel_number, { note: value ?? '' })
}

function saveTarget(deal: DealItem, value: number | null): void {
  void pipeline.updateDeal(deal.parcel_number, { target_price: value })
}
</script>

<template>
  <q-layout view="hHh Lpr fFf">
    <AppHeader title="Deal pipeline" />

    <q-page-container>
      <q-page class="pipeline-page">
        <q-inner-loading :showing="loading" color="primary" />
        <div v-if="!loading && deals.length === 0" class="empty">
          <q-icon name="view_kanban" size="48px" color="grey-4" />
          <div class="text-subtitle1 text-grey-7 q-mt-sm">Your pipeline is empty</div>
          <div class="text-body2 text-grey-6">
            Open a lot and tap “Add to pipeline” to start tracking a deal.
          </div>
          <q-btn
            class="q-mt-md"
            unelevated
            no-caps
            color="primary"
            label="Browse the map"
            :to="{ name: 'explore', params: { market: market.active } }"
          />
        </div>

        <div v-else class="board">
          <div
            v-for="stage in STAGES"
            :key="stage.value"
            class="column"
            :class="{ over: dragOver === stage.value }"
            @dragover.prevent="dragOver = stage.value"
            @dragleave="dragOver = null"
            @drop="onDrop($event, stage.value)"
          >
            <div class="column-head">
              <q-badge :color="stage.color" rounded class="q-mr-xs" />
              <span class="column-title">{{ stage.label }}</span>
              <q-space />
              <span class="column-count">{{ dealsIn(stage.value).length }}</span>
            </div>

            <div class="cards">
              <q-card
                v-for="deal in dealsIn(stage.value)"
                :key="deal.id"
                flat
                bordered
                class="deal lot-card"
                draggable="true"
                @dragstart="onDragStart($event, deal)"
                @dragend="dragging = null"
              >
                <div class="deal-head">
                  <div class="deal-addr ellipsis" @click="openParcel(deal)">
                    {{ deal.address ?? deal.parcel_number }}
                  </div>
                  <q-btn flat dense round size="sm" icon="more_vert">
                    <q-menu auto-close>
                      <q-list dense style="min-width: 170px">
                        <q-item-label header class="text-caption">Move to</q-item-label>
                        <q-item
                          v-for="target in STAGES"
                          :key="target.value"
                          clickable
                          :disable="target.value === deal.stage"
                          @click="pipeline.moveStage(deal.parcel_number, target.value)"
                        >
                          <q-item-section>{{ target.label }}</q-item-section>
                        </q-item>
                        <q-separator />
                        <q-item clickable @click="openParcel(deal)">
                          <q-item-section>Open on map</q-item-section>
                        </q-item>
                        <q-item clickable @click="pipeline.remove(deal.parcel_number)">
                          <q-item-section class="text-negative">Remove</q-item-section>
                        </q-item>
                      </q-list>
                    </q-menu>
                  </q-btn>
                </div>

                <div class="deal-meta">
                  <q-chip
                    v-if="deal.opportunity_score !== null"
                    dense
                    :color="scoreColor(deal.opportunity_score)"
                    text-color="white"
                    class="deal-score"
                  >
                    {{ deal.opportunity_score }}
                  </q-chip>
                  <span v-if="deal.base_zoning_code" class="deal-zone">{{ deal.base_zoning_code }}</span>
                </div>

                <div class="deal-target">
                  Target:
                  <span class="deal-target-value">{{ formatCurrency(deal.target_price) }}</span>
                  <q-popup-edit
                    v-slot="scope"
                    :model-value="deal.target_price"
                    buttons
                    @save="(value) => saveTarget(deal, value)"
                  >
                    <q-input
                      v-model.number="scope.value"
                      type="number"
                      label="Target price"
                      dense
                      autofocus
                    />
                  </q-popup-edit>
                </div>

                <div class="deal-note">
                  {{ deal.note || 'Add a note…' }}
                  <q-popup-edit
                    v-slot="scope"
                    :model-value="deal.note"
                    buttons
                    @save="(value) => saveNote(deal, value)"
                  >
                    <q-input v-model="scope.value" type="textarea" label="Note" dense autofocus autogrow />
                  </q-popup-edit>
                </div>
              </q-card>
            </div>
          </div>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.pipeline-page {
  position: relative;
  height: calc(100vh - 54px);
  height: calc(100dvh - 54px);
}
.board {
  display: flex;
  gap: 12px;
  height: 100%;
  overflow-x: auto;
  padding: 14px;
  align-items: flex-start;
}
.column {
  flex: 0 0 250px;
  background: var(--lot-bg);
  border-radius: var(--lot-radius);
  border: 1px solid var(--lot-border);
  max-height: 100%;
  display: flex;
  flex-direction: column;
  transition: background 0.12s ease;
}
.column.over {
  background: var(--lot-accent-soft);
  border-color: var(--lot-accent);
}
.column-head {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.column-title {
  font-weight: 700;
  color: var(--lot-muted);
}
.column-count {
  font-weight: 700;
  color: var(--lot-faint);
}
.cards {
  padding: 0 8px 8px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.deal {
  padding: 10px;
  cursor: grab;
}
.deal:active {
  cursor: grabbing;
}
.deal-head {
  display: flex;
  align-items: center;
}
.deal-addr {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  font-size: 13px;
  color: var(--lot-ink);
  cursor: pointer;
}
.deal-addr:hover {
  color: var(--q-primary);
}
.deal-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.deal-score {
  font-size: 11px;
}
.deal-zone {
  font-size: 12px;
  color: var(--lot-muted);
}
.deal-target {
  margin-top: 6px;
  font-size: 12px;
  color: var(--lot-muted);
  cursor: pointer;
}
.deal-target-value {
  font-weight: 600;
  color: var(--lot-ink);
}
.deal-note {
  margin-top: 6px;
  font-size: 12px;
  color: var(--lot-muted);
  cursor: pointer;
  white-space: pre-wrap;
}
.empty {
  text-align: center;
  padding: 60px 16px;
}
</style>
