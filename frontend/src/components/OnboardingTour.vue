<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'

import { useAuthStore } from '@/stores/auth'

interface Slide {
  icon: string
  title: string
  body: string
}

const SLIDES: Slide[] = [
  {
    icon: 'waving_hand',
    title: 'Welcome to LotScope',
    body: 'Everything you need to size up a Philadelphia lot — what can be built, what it’s worth, and what’s wrong with it — with the reasoning shown and sources cited.',
  },
  {
    icon: 'map',
    title: 'Explore the map',
    body: 'Browse vacant and infill lots on the map, filter by your buy box, and open any parcel to see its full dossier.',
  },
  {
    icon: 'insights',
    title: 'Read the Parcel Verdict',
    body: 'Each parcel gets an opportunity score blending buildability and risk. Tap “Why this score?” to see the breakdown and the flags behind it.',
  },
  {
    icon: 'inventory_2',
    title: 'Track your deals',
    body: 'Save lots to your watchlist and move promising ones through the pipeline — set next actions and due dates, and export to CSV.',
  },
]

const auth = useAuthStore()
const { user, isAuthenticated } = storeToRefs(auth)

const shouldShow = computed(
  () => isAuthenticated.value && !!user.value && user.value.onboarded_at === null,
)

const open = ref(false)
const step = ref(0)
const finishing = ref(false)

watch(
  shouldShow,
  (value) => {
    if (value) {
      step.value = 0
      open.value = true
    }
  },
  { immediate: true },
)

const slide = computed(() => SLIDES[step.value] ?? SLIDES[0])
const isLast = computed(() => step.value === SLIDES.length - 1)

function next(): void {
  if (isLast.value) void complete()
  else step.value += 1
}

function back(): void {
  if (step.value > 0) step.value -= 1
}

async function complete(): Promise<void> {
  open.value = false
  finishing.value = true
  try {
    await auth.markOnboarded()
  } finally {
    finishing.value = false
  }
}
</script>

<template>
  <q-dialog v-model="open" persistent>
    <q-card class="onboard-card">
      <q-card-section class="onboard-body">
        <q-icon :name="slide.icon" size="42px" color="primary" />
        <div class="onboard-title">{{ slide.title }}</div>
        <div class="onboard-text">{{ slide.body }}</div>
      </q-card-section>

      <div class="onboard-dots">
        <span
          v-for="(item, index) in SLIDES"
          :key="item.title"
          class="dot"
          :class="{ active: index === step }"
        />
      </div>

      <q-card-actions class="onboard-actions">
        <q-btn flat no-caps color="grey-7" label="Skip" @click="complete" />
        <q-space />
        <q-btn v-if="step > 0" flat no-caps label="Back" @click="back" />
        <q-btn
          unelevated
          no-caps
          color="primary"
          :label="isLast ? 'Get started' : 'Next'"
          @click="next"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.onboard-card {
  width: 420px;
  max-width: 92vw;
}
.onboard-body {
  text-align: center;
  padding: 28px 24px 8px;
}
.onboard-title {
  font-size: 20px;
  font-weight: 700;
  margin-top: 12px;
}
.onboard-text {
  font-size: 14px;
  color: var(--lot-muted);
  line-height: 1.5;
  margin-top: 8px;
}
.onboard-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
  padding: 4px 0;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--lot-border);
}
.dot.active {
  background: var(--q-primary);
}
.onboard-actions {
  padding: 12px 16px 16px;
}
</style>
