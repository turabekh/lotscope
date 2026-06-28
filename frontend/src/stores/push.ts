import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/lib/api'

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const normalized = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(normalized)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}

function subscriptionPayload(subscription: PushSubscription): {
  endpoint: string
  keys: { p256dh: string; auth: string }
} {
  const json = subscription.toJSON()
  return {
    endpoint: subscription.endpoint,
    keys: { p256dh: json.keys?.p256dh ?? '', auth: json.keys?.auth ?? '' },
  }
}

export const usePushStore = defineStore('push', () => {
  const supported = ref(
    typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window,
  )
  const enabled = ref(false)
  const busy = ref(false)
  const error = ref<string | null>(null)

  async function registration(): Promise<ServiceWorkerRegistration> {
    return navigator.serviceWorker.register('/sw.js')
  }

  async function refresh(): Promise<void> {
    if (!supported.value) return
    try {
      const reg = await registration()
      const subscription = await reg.pushManager.getSubscription()
      enabled.value = subscription !== null
    } catch {
      enabled.value = false
    }
  }

  async function enable(): Promise<void> {
    if (!supported.value || busy.value) return
    busy.value = true
    error.value = null
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        error.value = 'Notifications are blocked in your browser settings.'
        return
      }
      const { public_key: key } = await api.getVapidPublicKey()
      if (!key) {
        error.value = 'Push notifications are not available yet.'
        return
      }
      const reg = await registration()
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      })
      await api.pushSubscribe(subscriptionPayload(subscription))
      enabled.value = true
    } catch {
      error.value = 'Could not enable push notifications.'
    } finally {
      busy.value = false
    }
  }

  async function disable(): Promise<void> {
    if (busy.value) return
    busy.value = true
    error.value = null
    try {
      const reg = await registration()
      const subscription = await reg.pushManager.getSubscription()
      if (subscription) {
        await api.pushUnsubscribe(subscription.endpoint)
        await subscription.unsubscribe()
      }
      enabled.value = false
    } catch {
      error.value = 'Could not disable push notifications.'
    } finally {
      busy.value = false
    }
  }

  return { supported, enabled, busy, error, refresh, enable, disable }
})
