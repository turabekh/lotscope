<script setup lang="ts">
import { computed } from 'vue'

import type { SensitivityCell, SensitivityGrid } from '@/lib/types'

const props = defineProps<{ grid: SensitivityGrid | null }>()

const BASE = 1.0

function shiftLabel(multiplier: number, noun: string): string {
  const delta = Math.round((multiplier - 1) * 100)
  if (delta === 0) return `${noun} as modelled`
  return `${delta > 0 ? '+' : ''}${delta}% ${noun}`
}

const rows = computed(() => {
  const grid = props.grid
  if (!grid || !grid.available) return []
  return grid.exit_multipliers.map((exit) => ({
    exit,
    label: `${Math.round((exit - 1) * 100)}%`,
    cells: grid.cost_multipliers.map(
      (cost) =>
        grid.cells.find((c) => c.exit_multiplier === exit && c.cost_multiplier === cost) ?? null,
    ),
  }))
})

const columnLabels = computed(() =>
  (props.grid?.cost_multipliers ?? []).map((cost) => `${Math.round((cost - 1) * 100)}%`),
)

function toneOf(cell: SensitivityCell | null): string {
  if (cell === null) return 'tone-missing'
  if (cell.infeasible) return 'tone-dead'
  if (cell.margin === null) return 'tone-missing'
  if (cell.margin >= 0.2) return 'tone-strong'
  if (cell.margin >= 0.1) return 'tone-fair'
  if (cell.margin >= 0) return 'tone-thin'
  return 'tone-loss'
}

function isBase(cell: SensitivityCell | null): boolean {
  return cell !== null && cell.exit_multiplier === BASE && cell.cost_multiplier === BASE
}

function marginText(cell: SensitivityCell | null): string {
  if (cell === null || cell.margin === null) return '—'
  return `${Math.round(cell.margin * 100)}%`
}

function tooltipText(cell: SensitivityCell | null): string {
  if (cell === null) return 'Not modelled'
  if (cell.infeasible) return 'Not economical at any land price'
  const margin = cell.margin === null ? 'no margin' : `${Math.round(cell.margin * 100)}% margin`
  const profit =
    cell.profit === null
      ? ''
      : ` · ${cell.profit < 0 ? '−' : ''}$${Math.abs(Math.round(cell.profit)).toLocaleString()} profit`
  return `${shiftLabel(cell.exit_multiplier, 'finished value')}, ${shiftLabel(cell.cost_multiplier, 'build cost')} → ${margin}${profit}`
}
</script>

<template>
  <q-card v-if="grid" flat bordered class="rounded-borders">
    <q-card-section class="q-py-sm">
      <div class="section-title">
        <q-icon name="grid_on" size="18px" class="q-mr-xs" />What moves this deal
      </div>

      <div v-if="!grid.available" class="text-body2 text-grey-7" data-test="heatmap-unavailable">
        {{ grid.unavailable_reason }}
      </div>

      <template v-else>
        <p class="text-caption text-grey-7 q-mb-sm">
          Each cell is the margin if finished values land where the row says and build costs land
          where the column says. Your modelled case is outlined.
        </p>

        <div class="grid-scroll">
          <table class="heat" data-test="heatmap">
            <thead>
              <tr>
                <th class="corner">
                  <span class="axis-note">value ↓ / cost →</span>
                </th>
                <th v-for="label in columnLabels" :key="label" class="col-head">{{ label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.exit">
                <th class="row-head">{{ row.label }}</th>
                <td
                  v-for="(cell, index) in row.cells"
                  :key="index"
                  class="cell"
                  :class="[toneOf(cell), { 'is-base': isBase(cell) }]"
                >
                  <span class="cell-value">{{ marginText(cell) }}</span>
                  <q-tooltip max-width="250px" anchor="top middle" self="bottom middle">
                    {{ tooltipText(cell) }}
                  </q-tooltip>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </q-card-section>
  </q-card>
</template>

<style scoped>
.rounded-borders {
  border-radius: var(--lot-radius) !important;
  box-shadow: var(--lot-shadow);
}
.section-title {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--lot-muted);
  margin-bottom: 6px;
}
.grid-scroll {
  overflow-x: auto;
}
.heat {
  border-collapse: separate;
  border-spacing: 3px;
  width: 100%;
}
.corner {
  width: 68px;
}
.axis-note {
  font-size: 9px;
  font-weight: 500;
  color: var(--lot-muted);
  white-space: nowrap;
}
.col-head,
.row-head {
  font-size: 11px;
  font-weight: 600;
  color: var(--lot-muted);
  padding: 2px 4px;
}
.cell {
  position: relative;
  text-align: center;
  padding: 8px 4px;
  border-radius: 6px;
  min-width: 46px;
}
.cell-value {
  font-size: 12px;
  font-weight: 600;
}
.tone-strong {
  background: rgba(33, 150, 83, 0.26);
}
.tone-fair {
  background: rgba(33, 150, 83, 0.14);
}
.tone-thin {
  background: rgba(242, 201, 76, 0.22);
}
.tone-loss {
  background: rgba(235, 87, 87, 0.2);
}
.tone-dead {
  background: repeating-linear-gradient(
    45deg,
    rgba(130, 130, 130, 0.16),
    rgba(130, 130, 130, 0.16) 4px,
    transparent 4px,
    transparent 8px
  );
  color: var(--lot-muted);
}
.tone-missing {
  background: rgba(130, 130, 130, 0.08);
  color: var(--lot-muted);
}
.is-base {
  outline: 2px solid var(--lot-accent, #1976d2);
  outline-offset: -2px;
}
@media (max-width: 480px) {
  .cell {
    min-width: 38px;
    padding: 10px 2px;
  }
  .cell-value {
    font-size: 0;
  }
  .is-base .cell-value {
    font-size: 11px;
  }
}
</style>
