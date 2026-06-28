import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

// SSR=1 produce el bundle de servidor (dist-ssr/funnel-ssr.js) que exporta
// render(); sin SSR se hace el build cliente de siempre (dist/ + manifest).
const isSSR = !!process.env.SSR

export default defineConfig({
  plugins: [react()],
  // Base must match Django's STATIC_URL so collectstatic serves assets at /static/...
  base: '/static/',
  build: {
    // Inlining a 0 en AMBOS builds: en SSR los assets se referencian por URL de
    // archivo, mientras que el cliente por defecto inlinea los <4KB como data-URI.
    // Forzar 0 hace que el cliente también use URLs hasheadas → SSR y cliente
    // emiten exactamente la misma URL y no hay hydration mismatch.
    assetsInlineLimit: 0,
    ...(isSSR
      ? {
          ssr: 'src/funnel-ssr.jsx',
          outDir: 'dist-ssr',
          emptyOutDir: true,
        }
      : {
          manifest: true,
          outDir: 'dist',
          emptyOutDir: true,
          rollupOptions: {
            input: {
              funnel: resolve(__dirname, 'src/funnel-spa.jsx'),
            },
          },
        }),
  },
  // SSR: externalizamos las deps de node (default de Vite). jsdom —que trae
  // isomorphic-dompurify para sanitizar en servidor— hace require() de archivos
  // de datos por ruta relativa y NO se puede bundlear; por eso el servicio Node
  // corre con node_modules en vez de un bundle autocontenido. Solo nuestro
  // código fuente entra a funnel-ssr.js; React/jsdom/libphonenumber se resuelven
  // desde node_modules en runtime.
  ssr: {
    target: 'node',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Django (django-vite) busca el dev server fijo en :5173. strictPort hace
    // que Vite falle ruidosamente si 5173 está ocupado (p.ej. un Vite zombi) en
    // vez de derivar a 5174/5175 en silencio y dejar a Django sin bundle.
    strictPort: true,
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
