<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiError, api } from '@/lib/api'
import type { PacketRecord } from '@/lib/types'

const PACKET_PRICE = '$49'

const packets = ref<PacketRecord[]>([])
const purchasingEnabled = ref(true)
const loading = ref(true)
const busyId = ref<number | null>(null)
const error = ref<string | null>(null)

async function load(): Promise<void> {
  try {
    const [records, prices] = await Promise.all([api.getPackets(), api.getCheckoutPrices()])
    packets.value = records
    purchasingEnabled.value = prices.configured
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Your packets could not be loaded.'
  } finally {
    loading.value = false
  }
}

async function download(packet: PacketRecord): Promise<void> {
  busyId.value = packet.id
  error.value = null
  try {
    await api.downloadPacket(packet.id, packet.sale_date)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 402) {
      await buy(packet)
      return
    }
    if (cause instanceof ApiError && cause.status === 503) {
      purchasingEnabled.value = false
      error.value = cause.message
      return
    }
    error.value = cause instanceof ApiError ? cause.message : 'The download failed.'
  } finally {
    busyId.value = null
  }
}

async function buy(packet: PacketRecord): Promise<void> {
  busyId.value = packet.id
  error.value = null
  try {
    const session = await api.startCheckout('packet', String(packet.id))
    window.location.href = session.url
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Checkout could not start.'
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <q-page class="q-pa-md">
    <div class="packets-wrap">
      <div class="text-h5 text-weight-bold">Sale Packets</div>
      <div class="text-body2 lot-text-muted q-mb-md">
        Every vacant lot on a sheriff-sale date, screened against your buy box.
      </div>

      <div v-if="loading" class="text-body2 lot-text-muted">Loading…</div>

      <q-banner v-else-if="packets.length === 0" dense class="bg-blue-1" data-test="packets-empty">
        No packet yet. One is built for you before each sale date.
      </q-banner>

      <div v-else>
        <q-card
          v-for="packet in packets"
          :key="packet.id"
          flat
          bordered
          class="q-mb-sm"
          data-test="packet-card"
        >
          <q-card-section class="row items-center">
            <div>
              <div class="text-subtitle1">Sheriff sale {{ packet.sale_date }}</div>
              <div class="text-caption lot-text-muted">
                {{ packet.status === 'ready' ? 'Ready' : packet.status }}
              </div>
            </div>
            <q-space />
            <div v-if="packet.status === 'ready'" class="column items-end">
              <q-btn
                unelevated
                no-caps
                color="primary"
                :disable="!purchasingEnabled"
                :label="`Get this packet — ${PACKET_PRICE}`"
                :loading="busyId === packet.id"
                data-test="packet-buy"
                @click="download(packet)"
              />
              <div
                v-if="!purchasingEnabled"
                class="text-caption lot-text-muted q-mt-xs"
                data-test="packet-buy-soon"
              >
                Purchasing opens soon
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <q-banner v-if="error" dense class="bg-red-1 q-mt-md" data-test="packets-error">
        {{ error }}
      </q-banner>
    </div>
  </q-page>
</template>

<style scoped>
.packets-wrap {
  max-width: 720px;
  margin: 0 auto;
}
</style>
