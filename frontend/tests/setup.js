import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

/* Cada test arranca con el navegador "limpio": sin variantes guardadas, en la
   URL por defecto y sin mocks colgando del anterior. Es importante para los
   tests de A/B, donde una clave olvidada en localStorage haría pasar (o
   fallar) al siguiente por accidente. */
beforeEach(() => {
  // El funnel escribe ids de tracking por consola en cada montaje; en los tests
  // solo hace ruido y esconde los fallos de verdad.
  vi.spyOn(console, 'log').mockImplementation(() => {})
  localStorage.clear()
  window.history.replaceState({}, '', '/')
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
