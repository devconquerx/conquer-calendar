import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  // Base must match Django's STATIC_URL so collectstatic serves assets at /static/...
  base: '/static/',
  build: {
    manifest: true,
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/main.jsx'),
        landing: resolve(__dirname, 'src/landing.jsx'),
        video: resolve(__dirname, 'src/video.jsx'),
        confirmation: resolve(__dirname, 'src/confirmation.jsx'),
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allow HMR requests from Django's origin (localhost:8002 in local dev)
    cors: true,
    // Make JS-imported asset URLs absolute (http://localhost:5173/...) so they
    // resolve to the Vite dev server instead of Django's origin (8002) in dev.
    origin: 'http://localhost:5173',
    hmr: {
      host: 'localhost',
      port: 5173,
      protocol: 'ws',
    },
  },
})
