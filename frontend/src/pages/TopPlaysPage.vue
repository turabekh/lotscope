<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, api } from '@/lib/api'
import type { AssemblageTopPlay, AssemblageTopResponse } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const TOP_PLAYS_TIERS = ['pro', 'investor', 'enterprise']
const hasAccess = computed(() => TOP_PLAYS_TIERS.includes(user.value?.tier ?? 'free'))

const zoning = ref('')
const result = ref<AssemblageTopResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  if (!hasAccess.value) return
  loading.value = true
  error.value = null
  try {
    result.value = await api.getTopPlays({ zoning: zoning.value.trim() || undefined, limit: 200 })
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Could not load Top Plays.'
  } finally {
    loading.value = false
  }
}

function openPlay(play: AssemblageTopPlay): void {
  void router.push({ name: 'parcel', params: { id: play.parcel_number } })
}

function unitLabel(play: AssemblageTopPlay): string {
  if (play.unit_unlock == null) return '—'
  return `+${play.unit_unlock} unit${play.unit_unlock === 1 ? '' : 's'}`
}

function area(value: number | null): string {
  return value == null ? '—' : `${Math.round(value).toLocaleString('en-US')} sq ft`
}

onMounted(() => {
  if (hasAccess.value) void load()
})
</script>

<template>
  <q-page class="q-pa-md">
    <div class="plays-wrap">
      <div v-if="!hasAccess" class="upgrade">
        <q-icon name="dashboard_customize" size="52px" color="grey-4" />
        <div class="text-h6 q-mt-md">Assemblage Top Plays is a Pro feature</div>
        <div class="text-body2 text-grey-7 q-mb-md">
          A citywide, ranked feed of vacant lots where buying the parcel next door unlocks the most
          by-right units.
        </div>
        <q-btn unelevated no-caps color="primary" label="Upgrade" :to="{ name: 'account' }" />
      </div>

      <template v-else>
        <div class="row items-end q-col-gutter-md q-mb-md">
          <div class="col-auto">
            <div class="text-caption text-grey-7 q-mb-xs">Zoning class</div>
            <q-input
              v-model="zoning"
              outlined
              dense
              clearable
              placeholder="e.g. RM or RSA-5"
              style="min-width: 180px"
              @keyup.enter="load"
              @clear="load"
            >
              <template #append>
                <q-btn flat dense round icon="search" @click="load" />
              </template>
            </q-input>
          </div>
        </div>

        <q-banner v-if="error" dense class="bg-red-1 text-negative rounded-borders q-mb-md">
          {{ error }}
        </q-banner>

        <q-inner-loading :showing="loading" color="primary" />

        <q-list v-if="result && result.plays.length" bordered separator class="rounded-borders">
          <q-item
            v-for="play in result.plays"
            :key="play.parcel_number"
            v-ripple
            clickable
            @click="openPlay(play)"
          >
            <q-item-section avatar>
              <q-chip dense square color="deep-purple-6" text-color="white" icon="trending_up">
                {{ unitLabel(play) }}
              </q-chip>
            </q-item-section>
            <q-item-section>
              <q-item-label class="ellipsis">{{ play.address ?? play.parcel_number }}</q-item-label>
              <q-item-label caption class="ellipsis">
                {{ play.base_zoning_code ?? 'No zoning' }}
                <span v-if="play.neighborhood"> · {{ play.neighborhood }}</span>
                · {{ play.candidate_count }} candidate{{ play.candidate_count === 1 ? '' : 's' }}
              </q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-badge :color="play.potential === 'high' ? 'positive' : 'primary'" outline>
                {{ play.potential }}
              </q-badge>
              <div class="text-caption text-grey-6 q-mt-xs">
                {{ area(play.combined_lot_area_sqft) }}
              </div>
            </q-item-section>
          </q-item>
        </q-list>

        <div v-else-if="result && !loading" class="empty">
          <q-icon name="dashboard_customize" size="40px" color="grey-4" />
          <div class="text-body1 q-mt-sm">No assemblage plays found.</div>
          <div class="text-caption text-grey-6">Clear the zoning filter to see the full feed.</div>
        </div>

        <div
          v-if="result && result.returned < result.total"
          class="text-caption text-grey-6 q-mt-sm"
        >
          Showing the top {{ result.returned }} of {{ result.total }} plays.
        </div>
      </template>
    </div>
  </q-page>
</template>

<style scoped>
.plays-wrap {
  max-width: 860px;
  margin: 0 auto;
  position: relative;
}
.upgrade,
.empty {
  text-align: center;
  padding: 56px 20px;
}
</style>
