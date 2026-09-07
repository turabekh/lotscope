/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { quasar, transformAssetUrls } from '@quasar/vite-plugin'
import { defineConfig } from 'vite'

interface ProxyRes {
  headers: Record<string, string>
}

// Shared by the dev server and by `vite preview`, so a map that works while developing
// is a map that works in the build the browser tests drive.
const tileProxy = {
  '/tiles': {
    target: 'http://localhost:3000',
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/tiles/, ''),
    configure: (proxy: { on: (event: string, handler: (res: ProxyRes) => void) => void }) => {
      proxy.on('proxyRes', (proxyRes: ProxyRes) => {
        proxyRes.headers['cache-control'] = 'public, max-age=3600'
      })
    },
  },
}

export default defineConfig({
  plugins: [
    vue({ template: { transformAssetUrls } }),
    quasar({ sassVariables: fileURLToPath(new URL('./src/quasar-variables.sass', import.meta.url)) }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: { proxy: tileProxy },
  // The end-to-end suite runs against `vite preview`, which needs the same tiles.
  preview: { proxy: tileProxy },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.spec.ts'],
    env: { VITE_API_URL: 'http://127.0.0.1:9' },
  },
})
