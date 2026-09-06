<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  busy: boolean
  suggestion?: string | null
  saleDate?: string | null
}>()
const emit = defineEmits<{ send: [text: string]; stop: [] }>()

const text = ref('')

// The shortcuts only insert text. They are a faster way to type, not a second way to ask,
// so what runs is always exactly what the buyer can see in the box.
const SHORTCUTS = ['Screen the next sale', 'What changed on my lots'] as const

// "Screen the next sale" is only useful if the Analyst can resolve which sale that is.
// It can — get_sale_calendar — but when the server already knows the date, saying it is
// one fewer round trip and one fewer thing to get wrong.
//
// The date, not the server's suggested prompt: that prompt is whatever the opening asks
// for next, and for a buyer with no buy box it reads "I buy vacant lots in". A button
// labelled "Screen the next sale" that types something else is a button that lies.
function expand(shortcut: string): string {
  if (shortcut === 'Screen the next sale' && props.saleDate) {
    return `Screen the ${props.saleDate} sale against my buy box`
  }
  return shortcut
}

watch(
  () => props.suggestion,
  (value) => {
    if (value && !text.value) text.value = value
  },
  { immediate: true },
)

function submit(): void {
  const value = text.value.trim()
  if (!value || props.busy) return
  emit('send', value)
  text.value = ''
}

function insert(shortcut: string): void {
  text.value = expand(shortcut)
}
</script>

<template>
  <div class="composer">
    <div class="composer__shortcuts">
      <button
        v-for="shortcut in SHORTCUTS"
        :key="shortcut"
        type="button"
        class="composer__chip"
        data-test="composer-shortcut"
        @click="insert(shortcut)"
      >
        {{ shortcut }}
      </button>
    </div>
    <div class="composer__row">
      <textarea
        v-model="text"
        class="composer__input"
        rows="2"
        aria-label="Ask the Analyst"
        placeholder="Ask the Analyst"
        data-test="composer-input"
        @keydown.enter.exact.prevent="submit"
      ></textarea>
      <button
        v-if="busy"
        type="button"
        class="composer__send composer__send--stop"
        data-test="composer-stop"
        @click="emit('stop')"
      >
        Stop
      </button>
      <button
        v-else
        type="button"
        class="composer__send"
        :disabled="!text.trim()"
        data-test="composer-send"
        @click="submit"
      >
        Send
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  border-top: 1px solid var(--ls-line, #e0e0e0);
  padding: 8px 12px 12px;
  background: var(--ls-surface, #fff);
}
.composer__shortcuts {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.composer__chip {
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 999px;
  background: none;
  color: inherit;
  font: inherit;
  font-size: 12px;
  padding: 5px 11px;
  min-height: 32px;
  cursor: pointer;
}
.composer__row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.composer__input {
  flex: 1;
  resize: vertical;
  font: inherit;
  font-size: 13.5px;
  line-height: 1.45;
  padding: 8px 10px;
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 4px;
  background: var(--ls-surface, #fff);
  color: inherit;
}
.composer__send {
  min-height: 40px;
  padding: 0 16px;
  border: 0;
  border-radius: 4px;
  background: var(--ls-accent, #1565c0);
  color: #fff;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.composer__send:disabled {
  opacity: 0.45;
  cursor: default;
}
.composer__send--stop {
  background: var(--ls-muted, #6b7280);
}
</style>
