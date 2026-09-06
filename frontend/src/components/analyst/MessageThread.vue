<script setup lang="ts">
import { computed } from 'vue'

import AnalystAnswer from '@/components/analyst/AnalystAnswer.vue'
import FileCard from '@/components/analyst/FileCard.vue'
import ToolCard from '@/components/analyst/ToolCard.vue'
import type { ToolCall, Turn } from '@/stores/analyst'

const props = defineProps<{ turns: Turn[]; opening: string | null; streaming: boolean }>()
const emit = defineEmits<{ openLot: [parcelNumber: string, section: string | null] }>()

/** Files the Analyst produced, read off the envelopes rather than guessed at. */
function filesIn(turn: Turn): { label: string; detail: string | null; href: string | null }[] {
  const files: { label: string; detail: string | null; href: string | null }[] = []
  for (const call of turn.tools) {
    const data = call.envelope?.data ?? {}
    const path = (data.path ?? data.pdf_path ?? data.csv_path) as string | undefined
    if (!path) continue
    const packetId = data.packet_id as number | undefined
    files.push({
      label: String(path).split('/').pop() ?? path,
      detail: call.name.replace(/_/g, ' '),
      href: packetId ? `/packets` : null,
    })
  }
  return files
}

const hasTurns = computed(() => props.turns.length > 0)
</script>

<template>
  <div class="thread" data-test="analyst-thread">
    <div v-if="opening && !hasTurns" class="msg msg--analyst" data-test="analyst-opening">
      <div class="msg__who">Analyst</div>
      <p class="msg__text">{{ opening }}</p>
    </div>

    <div v-for="(turn, index) in turns" :key="turn.runId ?? `pending-${index}`" class="turn">
      <div class="msg msg--buyer">
        <div class="msg__who">You</div>
        <p class="msg__text">{{ turn.question }}</p>
      </div>

      <div class="msg msg--analyst">
        <div class="msg__who">Analyst</div>

        <ToolCard
          v-for="(call, position) in turn.tools"
          :key="`${call.name}-${position}`"
          :call="call as ToolCall"
          @open-lot="(parcel, section) => emit('openLot', parcel, section)"
        />

        <AnalystAnswer v-if="turn.answer" :text="turn.answer" />
        <p v-else-if="turn.status === 'running'" class="msg__pending" data-test="analyst-thinking">
          Working…
        </p>

        <FileCard
          v-for="file in filesIn(turn)"
          :key="file.label"
          :label="file.label"
          :detail="file.detail"
          :href="file.href"
        />

        <p v-if="turn.error" class="msg__error" data-test="analyst-error">{{ turn.error }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.thread {
  padding: 14px 16px 4px;
}
.turn + .turn {
  margin-top: 18px;
}
.msg + .msg {
  margin-top: 10px;
}
.msg__who {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ls-muted, #6b7280);
  margin-bottom: 3px;
}
.msg__text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 13.5px;
  max-width: 62ch;
}
.msg--buyer .msg__text {
  color: var(--ls-muted, #4b5563);
}
.msg__pending {
  margin: 0;
  color: var(--ls-muted, #6b7280);
  font-size: 13px;
}
.msg__error {
  margin: 6px 0 0;
  color: var(--ls-negative, #b91c1c);
  font-size: 13px;
}
</style>
