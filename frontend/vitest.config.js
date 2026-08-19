import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

/* Tests unitarios y de componente del funnel. Corren en jsdom (hay DOM,
   localStorage y URL) y NO tocan red ni backend: lo que se prueba aquí es la
   lógica del cliente. El recorrido real, con el bundle compilado y un navegador
   de verdad, va en tests/e2e (Playwright). */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    include: ['tests/unit/**/*.test.{js,jsx}', 'tests/component/**/*.test.{js,jsx}'],
    css: false,
    coverage: {
      provider: 'v8',
      include: ['src/lib/**', 'src/themes/**', 'src/components/landing/**', 'src/pages/**'],
      reporter: ['text-summary'],
    },
  },
})
