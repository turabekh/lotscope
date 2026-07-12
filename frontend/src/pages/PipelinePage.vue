<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import GenerateOfferDialog from '@/components/GenerateOfferDialog.vue'
import { ApiError, api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import type { DealActivityItem, DealItem, DealStage } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useCreditsStore } from '@/stores/credits'
import { useMarketStore } from '@/stores/market'
import { STAGES, usePipelineStore } from '@/stores/pipeline'

const $q = useQuasar()
const router = useRouter()
const market = useMarketStore()
const auth = useAuthStore()
const pipeline = usePipelineStore()
const credits = useCreditsStore()
const { user } = storeToRefs(auth)
const { deals, today, loading } = storeToRefs(pipeline)

const isFree = computed(() => (user.value?.tier ?? 'free') === 'free')
const exporting = ref(false)

async function exportCsv(): Promise<void> {
  exporting.value = true
  try {
    await api.exportPipeline()
  } catch {
    $q.notify({ type: 'negative', message: 'Export failed — try again in a moment.' })
  } finally {
    exporting.value = false
  }
}

const tab = ref<'board' | 'today'>($q.screen.lt.md ? 'today' : 'board')
const dragging = ref<string | null>(null)
const dragOver = ref<DealStage | null>(null)

const detailDeal = ref<DealItem | null>(null)
const detailOpen = ref(false)
const activity = ref<DealActivityItem[]>([])
const contactDraft = ref({ contact_name: '', contact_phone: '', contact_email: '' })
const offerOpen = ref(false)
const offerDeal = ref<DealItem | null>(null)

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

function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  const due = new Date(iso)
  due.setHours(0, 0, 0, 0)
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return Math.round((due.getTime() - now.getTime()) / 86_400_000)
}

function dueLabel(iso: string | null): string {
  const days = daysUntil(iso)
  if (days === null) return ''
  if (days < 0) return days === -1 ? '1 day overdue' : `${-days} days overdue`
  if (days === 0) return 'Due today'
  if (days === 1) return 'Due tomorrow'
  return `Due in ${days} days`
}

function dueColor(iso: string | null): string {
  const days = daysUntil(iso)
  if (days === null) return 'grey-5'
  if (days < 0) return 'negative'
  if (days <= 2) return 'warning'
  return 'primary'
}

function stageLabel(stage: DealStage): string {
  return STAGES.find((entry) => entry.value === stage)?.label ?? stage
}

function whenLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function activityText(item: DealActivityItem): string {
  if (item.kind === 'stage_change') {
    return `Moved ${stageLabel(item.from_stage as DealStage)} → ${stageLabel(item.to_stage as DealStage)}`
  }
  if (item.kind === 'offer_generated') {
    try {
      const payload = JSON.parse(item.body ?? '{}') as { offer_price?: number }
      const price = payload.offer_price != null ? formatCurrency(payload.offer_price) : ''
      return `Offer letter generated${price ? ` at ${price}` : ''}`
    } catch {
      return 'Offer letter generated'
    }
  }
  return item.body ?? 'Next action set'
}

function openOffer(deal: DealItem): void {
  offerDeal.value = deal
  offerOpen.value = true
}

function openParcel(deal: DealItem): void {
  void router.push({ name: 'parcel', params: { market: market.active, id: deal.parcel_number } })
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

function saveNextAction(deal: DealItem, value: string | null): void {
  void pipeline.updateDeal(deal.parcel_number, { next_action: value ?? '' })
}

function saveDue(deal: DealItem, value: string | null): void {
  void pipeline.updateDeal(deal.parcel_number, { next_action_due: value || null })
}

async function switchTab(value: string): Promise<void> {
  tab.value = value as 'board' | 'today'
  if (value === 'today') await pipeline.loadToday()
}

async function openDetail(deal: DealItem): Promise<void> {
  detailDeal.value = deal
  contactDraft.value = {
    contact_name: deal.contact_name ?? '',
    contact_phone: deal.contact_phone ?? '',
    contact_email: deal.contact_email ?? '',
  }
  activity.value = []
  traceProvenance.value = null
  detailOpen.value = true
  void credits.ensureLoaded()
  activity.value = await pipeline.loadActivity(deal.parcel_number)
}

async function saveContact(): Promise<void> {
  if (!detailDeal.value) return
  await pipeline.updateDeal(detailDeal.value.parcel_number, { ...contactDraft.value })
  detailOpen.value = false
}

const tracing = ref(false)
const traceProvenance = ref<string | null>(null)

async function skipTraceContact(): Promise<void> {
  if (!detailDeal.value) return
  tracing.value = true
  traceProvenance.value = null
  try {
    const result = await api.skipTrace(detailDeal.value.parcel_number)
    credits.set(result.credits_remaining)
    const phone = result.contacts.phones[0] ?? ''
    const email = result.contacts.emails[0] ?? ''
    if (!phone && !email) {
      $q.notify({ type: 'info', message: 'No contact info found — your credit was refunded.' })
      return
    }
    contactDraft.value = {
      contact_name: contactDraft.value.contact_name || (result.owner ?? ''),
      contact_phone: phone || contactDraft.value.contact_phone,
      contact_email: email || contactDraft.value.contact_email,
    }
    const provider = result.cached ? 'cached result' : 'skip trace'
    traceProvenance.value = `Filled via ${provider} · ${new Date().toLocaleDateString('en-US')}`
  } catch (cause) {
    $q.notify({
      type: 'negative',
      message: cause instanceof ApiError ? cause.message : 'Skip trace failed.',
    })
  } finally {
    tracing.value = false
  }
}
</script>

<template>
  <q-page class="pipeline-page">
    <div class="pipeline-header">
      <q-tabs v-model="tab" dense align="left" class="pipeline-tabs" @update:model-value="switchTab">
        <q-tab name="board" label="Board" no-caps />
        <q-tab name="today" label="Today" no-caps />
      </q-tabs>
      <q-space />
      <q-btn
        v-if="isFree"
        outline
        dense
        no-caps
        size="sm"
        color="primary"
        icon="lock"
        label="Export CSV"
        class="export-btn"
        :to="{ name: 'account' }"
      >
        <q-tooltip>CSV export is a Pro feature — upgrade to download your pipeline.</q-tooltip>
      </q-btn>
      <q-btn
        v-else
        dense
        no-caps
        size="sm"
        color="primary"
        icon="download"
        label="Export CSV"
        class="export-btn"
        :loading="exporting"
        :disable="deals.length === 0"
        @click="exportCsv"
      />
    </div>

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

    <div v-else-if="tab === 'today'" class="today-wrap">
      <div v-if="today.length === 0" class="empty">
        <q-icon name="event_available" size="42px" color="grey-4" />
        <div class="text-subtitle1 text-grey-7 q-mt-sm">Nothing due</div>
        <div class="text-body2 text-grey-6">Deals with a due date show up here when they’re due.</div>
      </div>
      <q-list v-else bordered separator class="today-list">
        <q-item v-for="deal in today" :key="deal.id" clickable @click="openParcel(deal)">
          <q-item-section>
            <q-item-label>{{ deal.address ?? deal.parcel_number }}</q-item-label>
            <q-item-label caption>
              {{ stageLabel(deal.stage) }}
              <span v-if="deal.next_action"> · {{ deal.next_action }}</span>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-chip dense square :color="dueColor(deal.next_action_due)" text-color="white">
              {{ dueLabel(deal.next_action_due) }}
            </q-chip>
          </q-item-section>
        </q-item>
      </q-list>
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
                    <q-item clickable @click="openDetail(deal)">
                      <q-item-section>Contact &amp; history</q-item-section>
                    </q-item>
                    <q-item clickable @click="openOffer(deal)">
                      <q-item-section>Generate offer</q-item-section>
                    </q-item>
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
              <span v-if="deal.base_zoning_code" class="deal-zone">{{
                deal.base_zoning_code
              }}</span>
            </div>

            <div v-if="deal.max_allowable_offer !== null || deal.est_profit !== null" class="deal-econ">
              <q-chip v-if="deal.max_allowable_offer !== null" dense square color="blue-grey-1">
                MAO {{ formatCurrency(deal.max_allowable_offer) }}
              </q-chip>
              <q-chip v-if="deal.est_profit !== null" dense square color="green-1">
                {{ formatCurrency(deal.est_profit) }} profit
              </q-chip>
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

            <div class="deal-next">
              <q-icon name="bolt" size="14px" />
              <span class="deal-next-text">{{ deal.next_action || 'Set next action…' }}</span>
              <q-popup-edit
                v-slot="scope"
                :model-value="deal.next_action"
                buttons
                @save="(value) => saveNextAction(deal, value)"
              >
                <q-input v-model="scope.value" label="Next action" dense autofocus />
              </q-popup-edit>
            </div>

            <div class="deal-due">
              <q-chip
                v-if="deal.next_action_due"
                dense
                square
                :color="dueColor(deal.next_action_due)"
                text-color="white"
              >
                {{ dueLabel(deal.next_action_due) }}
              </q-chip>
              <span v-else class="deal-due-empty">No due date</span>
              <q-popup-edit
                v-slot="scope"
                :model-value="deal.next_action_due"
                buttons
                @save="(value) => saveDue(deal, value)"
              >
                <q-input v-model="scope.value" type="date" label="Due date" dense autofocus />
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
                <q-input
                  v-model="scope.value"
                  type="textarea"
                  label="Note"
                  dense
                  autofocus
                  autogrow
                />
              </q-popup-edit>
            </div>
          </q-card>
        </div>
      </div>
    </div>

    <q-dialog v-model="detailOpen">
      <q-card class="detail-card">
        <q-card-section class="text-subtitle1">
          {{ detailDeal?.address ?? detailDeal?.parcel_number }}
        </q-card-section>
        <q-card-section class="q-gutter-sm">
          <div v-if="!market.isHidden('skip_trace')" class="row items-center q-gutter-sm">
            <q-btn
              outline
              no-caps
              dense
              color="primary"
              icon="person_search"
              label="Skip trace owner (1 credit)"
              :loading="tracing"
              @click="skipTraceContact"
            />
            <span v-if="credits.balance !== null" class="text-caption text-grey-7">
              {{ credits.balance }} credits
            </span>
          </div>
          <div v-if="traceProvenance" class="text-caption text-primary">{{ traceProvenance }}</div>
          <q-input v-model="contactDraft.contact_name" label="Contact name" dense />
          <q-input v-model="contactDraft.contact_phone" label="Phone" dense />
          <q-input v-model="contactDraft.contact_email" label="Email" dense />
          <div class="text-caption text-grey-6">
            Contact data is for real-estate outreach only — not for credit, employment, insurance, or
            tenant-screening decisions. Outreach is subject to TCPA / Do-Not-Call rules.
          </div>
        </q-card-section>
        <q-separator />
        <q-card-section>
          <div class="text-caption text-grey-7 q-mb-xs">History</div>
          <div v-if="activity.length === 0" class="text-body2 text-grey-6">No activity yet.</div>
          <q-list v-else dense>
            <q-item v-for="item in activity" :key="item.id">
              <q-item-section>
                <q-item-label>{{ activityText(item) }}</q-item-label>
                <q-item-label caption>{{ whenLabel(item.created_at) }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="Close" @click="detailOpen = false" />
          <q-btn unelevated no-caps color="primary" label="Save contact" @click="saveContact" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <GenerateOfferDialog
      v-if="offerDeal"
      v-model="offerOpen"
      :parcel-number="offerDeal.parcel_number"
      :max-allowable-offer="offerDeal.max_allowable_offer"
    />
  </q-page>
</template>

<style scoped>
.pipeline-page {
  position: relative;
  height: calc(100vh - 54px);
  height: calc(100dvh - 54px);
  display: flex;
  flex-direction: column;
}
.pipeline-header {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--lot-border);
  padding-right: 12px;
  flex: 0 0 auto;
}
.export-btn {
  margin-left: 8px;
}
.today-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}
.today-list {
  max-width: 720px;
  border-radius: var(--lot-radius);
}
.board {
  display: flex;
  gap: 12px;
  flex: 1;
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
@media (max-width: 1023px) {
  .board {
    flex-direction: column;
    overflow-x: visible;
    align-items: stretch;
  }
  .column {
    flex: 1 1 auto;
    width: 100%;
    max-height: none;
  }
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
.deal-econ {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
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
.deal-next {
  margin-top: 6px;
  font-size: 12px;
  color: var(--lot-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}
.deal-next-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.deal-due {
  margin-top: 6px;
  cursor: pointer;
}
.deal-due-empty {
  font-size: 12px;
  color: var(--lot-faint);
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
.detail-card {
  min-width: 340px;
  max-width: 460px;
}
</style>
