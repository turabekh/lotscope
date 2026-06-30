import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { Quasar, Dark, Notify } from 'quasar'

import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/src/css/index.sass'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@/css/tokens.css'
import '@/css/app.css'

import App from '@/App.vue'
import { router } from '@/router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(Quasar, { plugins: { Dark, Notify } })
app.mount('#app')
