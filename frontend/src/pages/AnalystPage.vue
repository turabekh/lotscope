<script setup lang="ts">
import { useQuasar } from 'quasar'
import { computed, onMounted, ref } from 'vue'

import AnalystComposer from '@/components/analyst/AnalystComposer.vue'
import ConversationList from '@/components/analyst/ConversationList.vue'
import EvidenceDrawer from '@/components/analyst/EvidenceDrawer.vue'
import MessageThread from '@/components/analyst/MessageThread.vue'
import { api } from '@/lib/api'
import type { BriefRecord } from '@/lib/types'
import { useAnalystStore } from '@/stores/analyst'

const $q = useQuasar()
const analyst = useAnalystStore()

const brief = ref<BriefRecord | null>(null)
const drawerParcel = ref<string | null>(null)
const railOpen = ref(false)

const isMobile = computed(() => $q.screen.lt.md)

onMounted(async () => {
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

function openLot(parcelNumber: string): void {
  drawerParcel.value = parcelNumber
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
      data-test="analyst-rail-toggle"
      @click="railOpen = !railOpen"
    >
      Conversations
    </button>

    <aside v-if="!isMobile || railOpen" class="analyst__rail">
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
        @send="analyst.send"
        @stop="analyst.cancel"
      />
    </main>

    <EvidenceDrawer
      v-if="drawerParcel"
      :parcel-number="drawerParcel"
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
  grid-template-columns: minmax(0, 1fr);
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
.analyst--mobile .analyst__rail {
  border-right: 0;
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
  max-height: 40vh;
}
.analyst--mobile .analyst__evidence {
  width: 100%;
}
</style>
