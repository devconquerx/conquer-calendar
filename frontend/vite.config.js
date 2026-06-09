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
        funnel: resolve(__dirname, 'src/funnel-spa.jsx'),
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    cors: true,
    origin: 'http://localhost:5173',
    hmr: {
      host: 'localhost',
      port: 5173,
      protocol: 'ws',
    },
    proxy: {
      '/f/': 'http://localhost:8002',
      '/agenda/': 'http://localhost:8002',
      '/panel/': 'http://localhost:8002',
      '/r/': 'http://localhost:8002',
      '/e/': 'http://localhost:8002',
      '/accounts/': 'http://localhost:8002',
    },
  },
})
