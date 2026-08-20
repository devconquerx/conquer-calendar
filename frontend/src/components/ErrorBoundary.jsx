import { Component } from 'react'

/**
 * Última línea de defensa del funnel.
 *
 * Sin esto, una excepción en el render de CUALQUIER componente desmonta el
 * árbol entero y el visitante ve una página en blanco: sin texto, sin
 * formulario y sin forma de saber qué pasó. Ocurrió de verdad —un acceso a
 * localStorage en un navegador que lo tiene bloqueado tumbaba la landing
 * completa— y volverá a ocurrir con otra causa distinta.
 *
 * El plan B es deliberadamente mínimo y autónomo: estilos en línea y cero
 * dependencias de contexto o de tema, porque justamente puede ser el tema o el
 * contexto lo que ha fallado.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { fallo: false }
  }

  static getDerivedStateFromError() {
    return { fallo: true }
  }

  componentDidCatch(error, info) {
    // Import perezoso: este archivo lo comparten cliente y SSR, y @sentry/react
    // toca APIs de navegador al cargarse. componentDidCatch sólo corre en el
    // cliente, así que aquí es seguro.
    import('@sentry/react')
      .then(({ captureException }) => {
        captureException(error, { extra: { componentStack: info?.componentStack } })
      })
      .catch(() => {})
    console.error('[Funnel] Fallo no recuperable en el render', error)
  }

  render() {
    if (!this.state.fallo) return this.props.children

    return (
      <div
        role="alert"
        style={{
          minHeight: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '1rem',
          padding: '2rem', textAlign: 'center',
          fontFamily: 'system-ui, -apple-system, sans-serif', color: '#1a1a1a',
        }}
      >
        <p style={{ margin: 0, fontSize: '1.05rem', maxWidth: '32rem' }}>
          No hemos podido cargar esta página en tu navegador.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            padding: '0.75rem 1.5rem', fontSize: '1rem', fontWeight: 600,
            border: 0, borderRadius: '0.5rem', cursor: 'pointer',
            background: '#1a1a1a', color: '#fff',
          }}
        >
          Reintentar
        </button>
      </div>
    )
  }
}
