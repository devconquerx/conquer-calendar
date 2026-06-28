import { createServer } from 'node:http'
import { render } from '../dist-ssr/funnel-ssr.js'

/* Servicio de render SSR del funnel. Stateless y sin dependencias propias: Django
   le hace POST /render con el payload de la etapa (stage, funnel_config, escuela,
   region, urls, search) y devuelve { html }. Si algo falla devuelve 500 y Django
   cae a CSR (root vacío). GET /health para el healthcheck del contenedor. */

const PORT = Number(process.env.PORT) || 3000
const MAX_BODY = 4 * 1024 * 1024 // 4MB: el funnel_config más grande cabe de sobra

const server = createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'content-type': 'text/plain' })
    res.end('ok')
    return
  }

  if (req.method === 'POST' && req.url === '/render') {
    let body = ''
    let aborted = false
    req.on('data', (chunk) => {
      body += chunk
      if (body.length > MAX_BODY) {
        aborted = true
        res.writeHead(413, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ error: 'payload too large' }))
        req.destroy()
      }
    })
    req.on('end', () => {
      if (aborted) return
      try {
        const props = JSON.parse(body || '{}')
        const html = render(props)
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ html }))
      } catch (err) {
        // Nunca tumbar el proceso por un payload malo: log + 500, Django hace fallback.
        console.error('[ssr] render error:', err && err.stack ? err.stack : err)
        res.writeHead(500, { 'content-type': 'application/json' })
        res.end(JSON.stringify({ error: String((err && err.message) || err) }))
      }
    })
    return
  }

  res.writeHead(404, { 'content-type': 'text/plain' })
  res.end('not found')
})

server.listen(PORT, () => {
  console.log(`[ssr] funnel SSR escuchando en :${PORT}`)
})
