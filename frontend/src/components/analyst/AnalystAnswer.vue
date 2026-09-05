<script setup lang="ts">
import { computed } from 'vue'

import { parseAnswer } from '@/components/analyst/answerBlocks'

const props = defineProps<{ text: string }>()
const blocks = computed(() => parseAnswer(props.text))
</script>

<template>
  <div class="answer" data-test="analyst-answer">
    <template v-for="(block, index) in blocks" :key="index">
      <p v-if="block.kind === 'paragraph'" class="answer__p">
        <template v-for="(span, position) in block.spans" :key="position">
          <strong v-if="span.bold">{{ span.text }}</strong>
          <template v-else>{{ span.text }}</template>
        </template>
      </p>

      <ul v-else-if="block.kind === 'list'" class="answer__list">
        <li v-for="(item, position) in block.items" :key="position">
          <template v-for="(span, at) in item" :key="at">
            <strong v-if="span.bold">{{ span.text }}</strong>
            <template v-else>{{ span.text }}</template>
          </template>
        </li>
      </ul>

      <div v-else class="answer__table-wrap">
        <table class="answer__table" data-test="analyst-table">
          <thead>
            <tr>
              <th v-for="(head, at) in block.header" :key="at">{{ head }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, at) in block.rows" :key="at">
              <td v-for="(cell, position) in row" :key="position">{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.answer {
  font-size: 13.5px;
  line-height: 1.55;
  max-width: 70ch;
}
.answer__p {
  margin: 0 0 8px;
}
.answer__list {
  margin: 0 0 8px;
  padding-left: 18px;
}
.answer__table-wrap {
  overflow-x: auto;
  margin: 0 0 10px;
}
.answer__table {
  border-collapse: collapse;
  font-size: 12.5px;
  min-width: 100%;
}
.answer__table th,
.answer__table td {
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
  padding: 4px 12px 4px 0;
  text-align: left;
  white-space: nowrap;
}
.answer__table th {
  color: var(--ls-muted, #6b7280);
  font-weight: 500;
}
</style>
