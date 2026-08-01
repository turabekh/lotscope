<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

interface ShowcaseRow {
  label: string
  value: string
  tone?: 'good' | 'warn' | 'bad'
}

interface ShowcasePanel {
  tab: string
  headline: string
  rows: ShowcaseRow[]
  chips?: string[]
  note: string
}

const PANELS: ShowcasePanel[] = [
  {
    tab: 'Verdict',
    headline: 'Base district · 3 units',
    rows: [
      { label: 'Buildability', value: 'Dimensionally eligible', tone: 'good' },
      { label: 'Est. land value', value: '$95K – $180K' },
      { label: 'Opportunity', value: '72 / 100', tone: 'good' },
    ],
    note: 'Preliminary screening, not a construction approval.',
  },
  {
    tab: 'Deal',
    headline: 'Max allowable offer $165,708',
    rows: [
      { label: 'ARV (finished)', value: '$490,000' },
      { label: 'All-in cost', value: '$326,292' },
      { label: 'Profit · margin', value: '$163,708 · 33%', tone: 'good' },
    ],
    note: 'Medium confidence · 25 comparable sales.',
  },
  {
    tab: 'Land',
    headline: 'RSA-5 · 1,000 sq ft lot',
    rows: [
      { label: 'By-right height', value: '38 ft · ~3 floors' },
      { label: 'Buildable area', value: '318 sq ft after setbacks' },
      { label: 'Frontage · depth', value: '16 ft · 62 ft' },
    ],
    note: 'Zoning resolved against Title 14 base-district standards.',
  },
  {
    tab: 'Risk',
    headline: 'Risk 20 / 100',
    chips: ['Tax delinquency', 'Historic overlay', 'RCO meeting required'],
    rows: [
      { label: 'Liens & taxes', value: '$22,000 owed · 4 years', tone: 'bad' },
      { label: 'Flood', value: 'Not in a FEMA flood zone', tone: 'good' },
      { label: 'L&I', value: 'No open violations', tone: 'good' },
    ],
    note: 'Six checks clear · one not evaluated.',
  },
  {
    tab: 'Comps',
    headline: '3 recorded sales nearby',
    rows: [
      { label: '1504 S Broad St', value: '84 ft · $110,000' },
      { label: '1506 S Broad St', value: '168 ft · $100,000' },
      { label: '1435 S Juniper St', value: '950 ft · $92,500' },
    ],
    note: 'Real recorded deeds, trimmed of outliers.',
  },
  {
    tab: 'Ask',
    headline: '“Can I build three units here?”',
    rows: [
      { label: 'Answer', value: 'Yes, under RSA-5 dimensional standards', tone: 'good' },
      { label: 'Cited', value: 'Title 14 §14-701 · §14-702' },
      { label: 'Confidence', value: 'High' },
    ],
    note: 'Every answer cites the code section it came from.',
  },
]

const ROTATE_MS = 4200

const index = ref(0)
const paused = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

const reducedMotion =
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

const trackStyle = computed(() => ({
  transform: `translateX(-${index.value * 100}%)`,
  transition: reducedMotion ? 'none' : 'transform 520ms cubic-bezier(0.22, 0.61, 0.36, 1)',
}))

function show(next: number): void {
  index.value = (next + PANELS.length) % PANELS.length
}

function start(): void {
  if (reducedMotion) return
  stop()
  timer = setInterval(() => {
    if (!paused.value) show(index.value + 1)
  }, ROTATE_MS)
}

function stop(): void {
  if (timer !== undefined) clearInterval(timer)
  timer = undefined
}

function select(next: number): void {
  show(next)
  start()
}

onMounted(start)
onBeforeUnmount(stop)
</script>

<template>
  <div
    class="showcase"
    data-test="hero-showcase"
    @mouseenter="paused = true"
    @mouseleave="paused = false"
    @focusin="paused = true"
    @focusout="paused = false"
  >
    <div class="sc-head">
      <div>
        <div class="sc-addr">1500 S Broad St</div>
        <div class="sc-sub">Parcel 88800001 · Philadelphia</div>
      </div>
      <span class="sc-tag">Example</span>
    </div>

    <div class="sc-tabs" role="tablist" aria-label="Example parcel views">
      <button
        v-for="(panel, i) in PANELS"
        :key="panel.tab"
        type="button"
        role="tab"
        class="sc-tab"
        :class="{ active: i === index }"
        :aria-selected="i === index"
        :data-test="`showcase-tab-${panel.tab.toLowerCase()}`"
        @click="select(i)"
      >
        {{ panel.tab }}
      </button>
    </div>

    <div class="sc-window">
      <div class="sc-track" :style="trackStyle">
        <section
          v-for="(panel, i) in PANELS"
          :key="panel.tab"
          class="sc-panel"
          role="tabpanel"
          :aria-hidden="i !== index"
        >
          <div class="sc-headline">{{ panel.headline }}</div>

          <div v-if="panel.chips" class="sc-chips">
            <span v-for="chip in panel.chips" :key="chip" class="sc-chip">{{ chip }}</span>
          </div>

          <div class="sc-rows">
            <div v-for="row in panel.rows" :key="row.label" class="sc-row">
              <span class="sc-label">{{ row.label }}</span>
              <span class="sc-value" :class="row.tone ? `tone-${row.tone}` : ''">
                {{ row.value }}
              </span>
            </div>
          </div>

          <div class="sc-note">{{ panel.note }}</div>
        </section>
      </div>
    </div>

    <div class="sc-progress" aria-hidden="true">
      <span
        v-for="(panel, i) in PANELS"
        :key="panel.tab"
        class="sc-dot"
        :class="{ on: i === index }"
      />
    </div>
  </div>
</template>

<style scoped>
.showcase {
  background: var(--lot-surface);
  color: var(--lot-ink);
  border: 1px solid var(--lot-border);
  border-radius: 14px;
  padding: 14px 14px 10px;
  box-shadow: 0 16px 34px rgba(8, 12, 24, 0.32);
  max-width: 440px;
  width: 100%;
}
.sc-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.sc-addr {
  font-weight: 700;
  font-size: 15px;
}
.sc-sub {
  font-size: 11.5px;
  color: var(--lot-muted);
  margin-top: 1px;
}
.sc-tag {
  font-size: 11px;
  font-weight: 700;
  border-radius: 6px;
  padding: 2px 7px;
  background: var(--lot-accent-soft);
  color: var(--lot-accent-ink, #4338ca);
  white-space: nowrap;
}
.sc-tabs {
  display: flex;
  gap: 2px;
  margin-top: 12px;
  overflow-x: auto;
  scrollbar-width: none;
}
.sc-tabs::-webkit-scrollbar {
  display: none;
}
.sc-tab {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--lot-muted);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 9px;
  border-radius: 8px;
  cursor: pointer;
  white-space: nowrap;
}
.sc-tab:hover {
  color: var(--lot-ink);
}
.sc-tab.active {
  background: var(--lot-accent-soft);
  color: var(--lot-accent-ink, var(--lot-accent));
}
.sc-window {
  overflow: hidden;
  margin-top: 10px;
}
.sc-track {
  display: flex;
  will-change: transform;
}
.sc-panel {
  flex: 0 0 100%;
  min-width: 100%;
  min-height: 148px;
  display: flex;
  flex-direction: column;
}
.sc-headline {
  font-size: 14.5px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.sc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}
.sc-chip {
  font-size: 10.5px;
  border-radius: 999px;
  padding: 3px 8px;
  background: rgba(239, 68, 68, 0.14);
  color: var(--lot-sev-high, #b91c1c);
}
.sc-rows {
  margin-top: 10px;
  display: grid;
  gap: 7px;
}
.sc-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12.5px;
}
.sc-label {
  color: var(--lot-muted);
  flex: none;
}
.sc-value {
  font-weight: 700;
  text-align: right;
}
.tone-good {
  color: var(--lot-score-positive, #15803d);
}
.tone-warn {
  color: var(--lot-sev-medium, #b45309);
}
.tone-bad {
  color: var(--lot-sev-high, #b91c1c);
}
.sc-note {
  margin-top: auto;
  padding-top: 10px;
  font-size: 11px;
  line-height: 1.45;
  color: var(--lot-muted);
}
.sc-progress {
  display: flex;
  gap: 4px;
  justify-content: center;
  margin-top: 8px;
}
.sc-dot {
  width: 14px;
  height: 3px;
  border-radius: 999px;
  background: var(--lot-border-strong, rgba(100, 116, 139, 0.5));
  transition: background 240ms ease;
}
.sc-dot.on {
  background: var(--lot-accent);
}
</style>
