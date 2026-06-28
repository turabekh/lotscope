self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = {}
  }
  const title = payload.title || 'LotScope PHL'
  const options = {
    body: payload.body || '',
    data: { url: payload.url || '/' },
    icon: '/favicon.ico',
    badge: '/favicon.ico',
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (client.url.includes(target) && 'focus' in client) return client.focus()
      }
      return self.clients.openWindow(target)
    }),
  )
})
