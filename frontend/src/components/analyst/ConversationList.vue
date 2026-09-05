<script setup lang="ts">
import type { BriefRecord, ConversationRead } from '@/lib/types'

defineProps<{
  conversations: ConversationRead[]
  activeId: number | null
  brief: BriefRecord | null
}>()
const emit = defineEmits<{ open: [id: number]; openBrief: []; startNew: [] }>()
</script>

<template>
  <nav class="rail" aria-label="Conversations">
    <button type="button" class="rail__new" data-test="analyst-new" @click="emit('startNew')">
      New conversation
    </button>

    <button
      v-if="brief"
      type="button"
      class="rail__item rail__item--brief"
      data-test="analyst-brief-pin"
      @click="emit('openBrief')"
    >
      <span class="rail__title">Today's brief</span>
      <span class="rail__meta">
        {{ brief.signal_count }} change{{ brief.signal_count === 1 ? '' : 's' }} ·
        {{ brief.brief_date }}
      </span>
    </button>

    <button
      v-for="conversation in conversations"
      :key="conversation.id"
      type="button"
      class="rail__item"
      :class="{ 'rail__item--on': conversation.id === activeId }"
      data-test="analyst-conversation"
      @click="emit('open', conversation.id)"
    >
      <span class="rail__title">{{ conversation.title ?? 'Untitled' }}</span>
      <span class="rail__meta">{{ conversation.updated_at.slice(0, 10) }}</span>
    </button>

    <p v-if="!conversations.length" class="rail__empty">No conversations yet.</p>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 8px;
  overflow-y: auto;
  height: 100%;
}
.rail__new {
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 4px;
  background: none;
  color: inherit;
  font: inherit;
  font-size: 12.5px;
  padding: 8px;
  min-height: 36px;
  cursor: pointer;
  margin-bottom: 8px;
}
.rail__item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  text-align: left;
  border: 0;
  border-radius: 4px;
  background: none;
  color: inherit;
  font: inherit;
  padding: 7px 8px;
  min-height: 40px;
  cursor: pointer;
}
.rail__item--on {
  background: var(--ls-selected, #eef2f7);
}
.rail__item--brief {
  border: 1px solid var(--ls-line, #e0e0e0);
  margin-bottom: 8px;
}
.rail__title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail__meta,
.rail__empty {
  font-size: 11px;
  color: var(--ls-muted, #6b7280);
}
.rail__empty {
  padding: 8px;
}
</style>
