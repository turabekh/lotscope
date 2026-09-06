<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AnalystComposer from '@/components/analyst/AnalystComposer.vue'
import ConversationList from '@/components/analyst/ConversationList.vue'
import EvidenceDrawer from '@/components/analyst/EvidenceDrawer.vue'
import MessageThread from '@/components/analyst/MessageThread.vue'
import { api } from '@/lib/api'
import { isLotSection, type LotSection } from '@/lib/sourceLinks'
import type { BriefRecord } from '@/lib/types'
import { openingQuestionFor, openingQuestionForMany } from '@/components/analyst/askAboutLot'
import { useAnalystStore } from '@/stores/analyst'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const analyst = useAnalystStore()

const brief = ref<BriefRecord | null>(null)
const drawerParcel = ref<string | null>(null)
const drawerSection = ref<LotSection | null>(null)
const railOpen = ref(false)

const isMobile = computed(() => $q.screen.lt.md)

onMounted(async () => {
  // A lot handed over from the Lot page starts the conversation already about that lot.
  const about = route.query.about
  const label = route.query.label
  if (typeof about === 'string' && about) {
    // Deals hands over several parcels at once, comma separated.
    const labels = (typeof label === 'string' && label ? label : about)
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean)
    const question = openingQuestionForMany(labels) || openingQuestionFor(about)
    void router.replace({ name: 'analyst' })
    void analyst.send(question)
  }

  await Promise.all([
    analyst.loadConversations(),
    analyst.loadOpening(),
    api
      .todaysBrief()
      .then((value) => {
        brief.value = value
      })
      .catch(() => {
        brief.value = null
      }),
  ])
})

function openLot(parcelNumber: string, section: string | null): void {
  drawerParcel.value = parcelNumber
  drawerSection.value = section && isLotSection(section) ? section : null
}

async function openConversation(id: number): Promise<void> {
  railOpen.value = false
  await analyst.openConversation(id)
}

function startNew(): void {
  railOpen.value = false
  analyst.startNew()
}

/** The brief is a message in the thread, not a separate screen. */
function openBrief(): void {
  railOpen.value = false
  if (!brief.value) return
  analyst.startNew()
  analyst.turns.push({
    runId: null,
    question: "What's in today's brief?",
    answer: brief.value.text,
    status: 'succeeded',
    tools: [],
    error: null,
  })
}
</script>

<template>
  <div class="analyst" :class="{ 'analyst--mobile': isMobile }">
    <button
      v-if="isMobile"
      type="button"
      class="analyst__rail-toggle"
      :aria-expanded="railOpen"
      data-test="analyst-rail-toggle"
      @click="railOpen = !railOpen"
    >
      Conversations
      <span aria-hidden="true">{{ railOpen ? '⌃' : '⌄' }}</span>
    </button>

    <!-- On a phone the rail is a sheet over the thread, dismissed by tapping away from it.
         As a row of the layout it took a third of the screen to show nothing. -->
    <button
      v-if="isMobile && railOpen"
      type="button"
      class="analyst__scrim"
      aria-label="Close conversations"
      data-test="analyst-rail-scrim"
      @click="railOpen = false"
    ></button>

    <aside
      v-if="!isMobile || railOpen"
      class="analyst__rail"
      :class="{ 'analyst__rail--sheet': isMobile }"
    >
      <ConversationList
        :conversations="analyst.conversations"
        :active-id="analyst.conversationId"
        :brief="brief"
        @open="openConversation"
        @open-brief="openBrief"
        @start-new="startNew"
      />
    </aside>

    <main class="analyst__centre">
      <div class="analyst__scroll">
        <MessageThread
          :turns="analyst.turns"
          :opening="analyst.opening?.text ?? null"
          :streaming="analyst.streaming"
          @open-lot="openLot"
        />
      </div>
      <AnalystComposer
        :busy="analyst.streaming"
        :suggestion="analyst.opening?.suggested_prompt ?? null"
        :sale-date="analyst.opening?.next_sale_date ?? null"
        @send="analyst.send"
        @stop="analyst.cancel"
      />
    </main>

    <EvidenceDrawer
      v-if="drawerParcel"
      :parcel-number="drawerParcel"
      :section="drawerSection"
      :bottom-sheet="isMobile"
      class="analyst__evidence"
      @close="drawerParcel = null"
    />
  </div>
</template>

<style scoped>
.analyst {
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr) auto;
  height: calc(100vh - var(--ls-topbar, 48px));
  overflow: hidden;
}
.analyst__rail {
  border-right: 1px solid var(--ls-line, #e0e0e0);
  overflow: hidden;
}
.analyst__centre {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.analyst__scroll {
  flex: 1;
  overflow-y: auto;
}
.analyst__evidence {
  width: min(460px, 40vw);
}
.analyst__rail-toggle {
  display: none;
}

.analyst--mobile {
  /* Rows, not an even split: the toggle is as tall as it needs to be and the thread gets
     everything else. Without this the button shared the height and left a third of the
     screen empty. */
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  position: relative;
}
.analyst--mobile .analyst__rail-toggle {
  display: block;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
  background: none;
  color: inherit;
  font: inherit;
  font-size: 13px;
  min-height: 40px;
  cursor: pointer;
}
.analyst__scrim {
  position: absolute;
  inset: 0;
  z-index: 8;
  border: 0;
  padding: 0;
  background: rgba(15, 23, 42, 0.35);
}
.analyst--mobile .analyst__rail--sheet {
  position: absolute;
  top: 40px;
  left: 0;
  right: 0;
  z-index: 9;
  border-right: 0;
  border-bottom: 1px solid var(--ls-line);
  background: var(--ls-surface);
  max-height: 60vh;
  overflow-y: auto;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
}
.analyst--mobile .analyst__evidence {
  width: 100%;
}
</style>
