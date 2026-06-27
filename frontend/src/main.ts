import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { Quasar, Notify } from 'quasar'

import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/src/css/index.sass'
import 'maplibre-gl/dist/maplibre-gl.css'

import App from '@/App.vue'
import { router } from '@/router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(Quasar, { plugins: { Notify } })
app.mount('#app')
