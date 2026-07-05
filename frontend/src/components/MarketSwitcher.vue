<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MARKETS, MARKET_LABELS, type Market, useMarketStore } from '@/stores/market'

withDefaults(defineProps<{ collapsed?: boolean; variant?: 'sidebar' | 'pill' }>(), {
  collapsed: false,
  variant: 'sidebar',
})

const route = useRoute()
const router = useRouter()
const market = useMarketStore()

const sheet = ref(false)
const activeLabel = computed(() => MARKET_LABELS[market.active])
const activePilot = computed(() => market.statusOf(market.active) === 'pilot')
const options = computed(() =>
  MARKETS.map((value) => ({
    value,
    label: MARKET_LABELS[value],
    pilot: market.statusOf(value) === 'pilot',
  })),
)

function switchTo(next: Market): void {
  sheet.value = false
  if (next === market.active) return
  if (route.params.market !== undefined && route.name) {
    void router.push({
      name: route.name,
      params: { ...route.params, market: next },
      query: route.query,
    })
  } else {
    void router.push({ name: 'home', params: { market: next } })
  }
}
</script>

<template>
  <q-btn
    v-if="variant === 'pill'"
    flat
    dense
    no-caps
    class="pill"
    aria-label="Switch market"
    @click="sheet = true"
  >
    <q-icon name="location_on" size="16px" class="switcher-pin" />
    <span class="pill-label">{{ activeLabel }}</span>
    <q-badge v-if="activePilot" color="amber-8" text-color="white" label="pilot" class="q-ml-xs" />
    <q-icon name="expand_more" size="15px" class="switcher-caret" />
    <q-dialog v-model="sheet" position="bottom">
      <q-card class="sheet-card">
        <q-card-section class="text-subtitle2 text-weight-bold">Market</q-card-section>
        <q-separator />
        <q-list>
          <q-item
            v-for="opt in options"
            :key="opt.value"
            v-close-popup
            clickable
            :active="opt.value === market.active"
            active-class="opt-active"
            @click="switchTo(opt.value)"
          >
            <q-item-section avatar><q-icon name="location_on" size="18px" /></q-item-section>
            <q-item-section>{{ opt.label }}<q-badge v-if="opt.pilot" color="amber-8" text-color="white" label="pilot" class="q-ml-sm" /></q-item-section>
            <q-item-section v-if="opt.value === market.active" side>
              <q-icon name="check" size="16px" />
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>
    </q-dialog>
  </q-btn>

  <q-btn
    v-else
    flat
    no-caps
    class="switcher"
    :class="{ mini: collapsed }"
    aria-label="Switch market"
  >
    <q-icon name="location_on" size="18px" class="switcher-pin" />
    <span v-if="!collapsed" class="switcher-label">{{ activeLabel }}</span>
    <q-badge v-if="activePilot && !collapsed" color="amber-8" text-color="white" label="pilot" class="q-mr-xs" />
    <q-icon v-if="!collapsed" name="expand_more" size="16px" class="switcher-caret" />
    <q-tooltip v-if="collapsed" anchor="center right" self="center left">{{
      activeLabel
    }}</q-tooltip>
    <q-menu anchor="bottom left" self="top left" fit>
      <q-list style="min-width: 180px">
        <q-item
          v-for="opt in options"
          :key="opt.value"
          v-close-popup
          clickable
          :active="opt.value === market.active"
          active-class="opt-active"
          @click="switchTo(opt.value)"
        >
          <q-item-section avatar><q-icon name="location_on" size="18px" /></q-item-section>
          <q-item-section>{{ opt.label }}<q-badge v-if="opt.pilot" color="amber-8" text-color="white" label="pilot" class="q-ml-sm" /></q-item-section>
          <q-item-section v-if="opt.value === market.active" side>
            <q-icon name="check" size="16px" />
          </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </q-btn>
</template>

<style scoped>
.switcher {
  width: 100%;
  justify-content: flex-start;
  padding: 8px 10px;
  border: 1px solid var(--lot-border);
  border-radius: var(--lot-radius-sm);
  background: var(--lot-accent-soft);
  color: var(--lot-accent-ink);
  font-weight: 600;
}
.switcher.mini {
  justify-content: center;
  padding: 8px 0;
}
.switcher-label {
  flex: 1;
  text-align: left;
  margin-left: 8px;
  font-size: 13px;
}
.pill {
  padding: 5px 9px;
  border: 1px solid var(--lot-border-accent, var(--lot-border));
  border-radius: var(--lot-radius-sm);
  background: var(--lot-accent-soft);
  color: var(--lot-accent-ink);
  font-weight: 600;
  gap: 4px;
}
.pill-label {
  font-size: 12px;
}
.switcher-pin {
  color: var(--lot-accent);
}
.switcher-caret {
  color: var(--lot-accent);
}
.sheet-card {
  width: 100%;
  border-top-left-radius: var(--lot-radius);
  border-top-right-radius: var(--lot-radius);
}
.opt-active {
  color: var(--lot-accent-ink);
  background: var(--lot-accent-soft);
}
</style>
