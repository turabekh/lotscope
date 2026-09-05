<script setup lang="ts">
import { computed, ref } from 'vue'

import { internalParcel, toolSummary } from '@/components/analyst/toolSummary'
import type { ToolCall } from '@/stores/analyst'

const props = defineProps<{ call: ToolCall }>()
const emit = defineEmits<{ openLot: [parcelNumber: string] }>()

const expanded = ref(false)
const summary = computed(() => toolSummary(props.call))
const sources = computed(() => props.call.envelope?.sources ?? [])
const unverified = computed(() => props.call.envelope?.unverified ?? [])

const MAX_NESTED_ROWS = 12
const MAX_NESTED_COLUMNS = 5

interface Field {
  key: string
  value: string | null
  table: { header: string[]; rows: string[][]; more: number } | null
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/**
 * The envelope's data as fields.
 *
 * A list of objects — the lots in a screen, the violations in a live read — becomes a small
 * table. Stringifying it produces a wall of JSON that buries the answer, which is the
 * opposite of what an evidence panel is for.
 */
const rows = computed<Field[]>(() => {
  const data = props.call.envelope?.data ?? {}
  return Object.entries(data).map(([key, value]) => {
    const label = key.replace(/_/g, ' ')
    if (
      Array.isArray(value) &&
      value.length > 0 &&
      value.every((item) => item !== null && typeof item === 'object' && !Array.isArray(item))
    ) {
      const records = value as Record<string, unknown>[]
      const header: string[] = []
      for (const record of records) {
        for (const field of Object.keys(record)) {
          if (!header.includes(field) && header.length < MAX_NESTED_COLUMNS) header.push(field)
        }
      }
      return {
        key: label,
        value: null,
        table: {
          header,
          rows: records
            .slice(0, MAX_NESTED_ROWS)
            .map((record) => header.map((field) => cell(record[field]))),
          more: Math.max(0, records.length - MAX_NESTED_ROWS),
        },
      }
    }
    return { key: label, value: cell(value), table: null }
  })
})

function stamp(source: { fetched_at: string | null; ingested_at: string | null }): string {
  if (source.fetched_at) return `read ${source.fetched_at.slice(0, 16).replace('T', ' ')} UTC`
  if (source.ingested_at) return `ingested ${source.ingested_at.slice(0, 16).replace('T', ' ')} UTC`
  return ''
}

function onSource(url: string | null): void {
  const parcel = internalParcel(url)
  if (parcel) emit('openLot', parcel)
}
</script>

<template>
  <div class="tool" :class="{ 'tool--running': call.running }" data-test="tool-card">
    <button
      class="tool__head"
      type="button"
      :aria-expanded="expanded"
      data-test="tool-card-toggle"
      @click="expanded = !expanded"
    >
      <span class="tool__mark" aria-hidden="true">{{ call.running ? '◌' : '▸' }}</span>
      <span class="tool__summary">{{ summary }}</span>
      <span v-if="call.durationMs !== null" class="tool__ms">{{ call.durationMs }}ms</span>
    </button>

    <div v-if="expanded" class="tool__body" data-test="tool-card-body">
      <table v-if="rows.length" class="tool__table">
        <tbody>
          <tr v-for="row in rows" :key="row.key">
            <th scope="row">{{ row.key }}</th>
            <td>
              <template v-if="row.table">
                <div class="tool__nested-wrap">
                  <table class="tool__nested" data-test="tool-nested-table">
                    <thead>
                      <tr>
                        <th v-for="head in row.table.header" :key="head">
                          {{ head.replace(/_/g, ' ') }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(nested, at) in row.table.rows" :key="at">
                        <td v-for="(value, position) in nested" :key="position">{{ value }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="row.table.more" class="tool__more">and {{ row.table.more }} more</div>
              </template>
              <template v-else>{{ row.value }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="tool__none">This tool returned no fields.</p>

      <div v-if="sources.length" class="tool__sources">
        <div class="tool__label">Sources</div>
        <ul>
          <li v-for="source in sources" :key="source.name + (source.url ?? '')">
            <button
              v-if="internalParcel(source.url)"
              type="button"
              class="tool__link"
              data-test="tool-source-internal"
              @click="onSource(source.url)"
            >
              {{ source.name }}
            </button>
            <a
              v-else-if="source.url"
              :href="source.url"
              target="_blank"
              rel="noopener"
              class="tool__link"
              data-test="tool-source-external"
              >{{ source.name }}</a
            >
            <span v-else>{{ source.name }}</span>
            <span class="tool__stamp">{{ stamp(source) }}</span>
          </li>
        </ul>
      </div>

      <div v-if="unverified.length" class="tool__unverified" data-test="tool-unverified">
        <div class="tool__label">Unverified</div>
        <ul>
          <li v-for="note in unverified" :key="note">{{ note }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool {
  border: 1px solid var(--ls-line, #e0e0e0);
  border-radius: 4px;
  margin: 6px 0;
  background: var(--ls-surface, #fff);
}
.tool--running {
  opacity: 0.75;
}
.tool__head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  background: none;
  border: 0;
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  color: inherit;
  min-height: 36px;
}
.tool__mark {
  color: var(--ls-muted, #6b7280);
}
.tool__summary {
  flex: 1;
}
.tool__ms,
.tool__stamp {
  color: var(--ls-muted, #6b7280);
  font-size: 11px;
}
.tool__body {
  border-top: 1px solid var(--ls-line, #e0e0e0);
  padding: 8px 10px 10px;
  font-size: 12.5px;
}
.tool__table {
  width: 100%;
  border-collapse: collapse;
}
.tool__table th {
  text-align: left;
  font-weight: 500;
  color: var(--ls-muted, #6b7280);
  padding: 2px 10px 2px 0;
  vertical-align: top;
  white-space: nowrap;
}
.tool__table td {
  padding: 2px 0;
  word-break: break-word;
}
.tool__label {
  color: var(--ls-muted, #6b7280);
  margin: 8px 0 2px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.tool__sources ul,
.tool__unverified ul {
  margin: 0;
  padding-left: 14px;
}
.tool__sources li {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.tool__link {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--ls-link, #1565c0);
  text-decoration: underline;
  cursor: pointer;
}
.tool__nested-wrap {
  overflow-x: auto;
  max-width: 100%;
}
.tool__nested {
  border-collapse: collapse;
  font-size: 11.5px;
}
.tool__nested th,
.tool__nested td {
  border-bottom: 1px solid var(--ls-line, #e0e0e0);
  padding: 2px 10px 2px 0;
  text-align: left;
  white-space: nowrap;
  max-width: 26ch;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tool__more {
  color: var(--ls-muted, #6b7280);
  font-size: 11px;
  padding-top: 2px;
}
.tool__none {
  margin: 0;
  color: var(--ls-muted, #6b7280);
}
</style>
