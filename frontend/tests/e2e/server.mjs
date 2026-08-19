/* Servidor mínimo para los e2e: sirve el bundle compilado (dist) bajo /static/
   y genera el mismo shell HTML que emite Django (pages/public/funnel/spa.html),
   con sus data-* y el <script id="funnel-config">.

   Así el recorrido se prueba contra el JS real que se despliega, sin levantar
   Docker ni Django. El backend se simula desde los propios tests con
   page.route(), que además permite afirmar QUÉ se envía en cada POST. */
import { createServer } from 'node:http'
import { readFile, readdir } from 'node:fs/promises'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = fileURLToPath(new URL('../../', import.meta.url))
const DIST = join(RAIZ, 'dist')
const PUERTO = Number(process.env.E2E_PORT || 4173)

const TIPOS = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.avif': 'image/avif', '.webp': 'image/webp',
  '.json': 'application/json', '.woff2': 'font/woff2', '.otf': 'font/otf', '.mp4': 'video/mp4' }

const CONFIG_FUNNEL = {
  landing: {
    title: 'Titular de prueba', subtitle: 'Vídeo gratis de 15 minutos', description: 'descripción',
    bullets: ['uno', 'dos', 'tres'], buttonText: 'Ver vídeo gratis',
    instructor: { name: 'Instructor', role: 'Rol', description: 'bio' }, disclaimer: '*aviso',
  },
  video: { videoUrls: ['/static/assets/vacio.mp4'], buttonPercent: 1 },
  blocks: [
    { name: 'welcome-screen', id: 'welcome', attributes: { label: 'Bienvenido', buttonText: 'Comenzar' } },
    { name: 'short-text', id: 'name', attributes: { label: 'Nombre', required: true } },
    { name: 'email', id: 'email', attributes: { label: 'Tu mejor correo', required: true } },
    { name: 'phone-number', id: 'phone', attributes: { label: 'Número de teléfono', required: true } },
    { name: 'multiple-choice', id: 'age', attributes: { label: '¿Qué edad tienes?', required: true,
      choices: [{ label: 'Tengo entre 25 y 34 años.', value: 'Tengo entre 25 y 34 años.' }, { label: 'Soy menor de 18 años.', value: 'Soy menor de 18 años.' }] } },
  ],
  q_order: ['age'],
}

async function activos() {
  const ficheros = await readdir(join(DIST, 'assets'))
  return {
    js: ficheros.find((f) => /^funnel-.*\.js$/.test(f)),
    css: ficheros.find((f) => /^funnel-.*\.css$/.test(f)),
  }
}

function shell({ js, css }, p) {
  const stage = p.get('stage') || 'landing'
  const slug = p.get('slug') || 'blocks-latam'
  const escuela = p.get('escuela') || 'conquer-blocks'
  const region = p.get('region') || 'latam'
  const video = p.get('video') === '1' ? '1' : '0'
  const q = `?slug=${slug}&escuela=${escuela}&region=${region}&video=${video}&stage=`
  return `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>${slug} — ${stage}</title><link rel="stylesheet" href="/static/assets/${css}">
<script type="module" crossorigin src="/static/assets/${js}"></script></head><body>
<script>window.__CQX_CALENDAR_ORIGIN__ = "";</script>
<script id="funnel-config" type="application/json">${JSON.stringify(CONFIG_FUNNEL)}</script>
<div id="funnel-root" data-slug="${slug}" data-csrf="test" data-escuela="${escuela}" data-region="${region}"
 data-program="fullstack" data-stage="${stage}" data-video-enabled="${video}"
 data-landing-url="/etapa${q}landing" data-video-url="/etapa${q}video"
 data-stepform-url="/etapa${q}stepform" data-confirmation-url="/etapa${q}confirmation"></div>
</body></html>`
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PUERTO}`)
  try {
    if (url.pathname.startsWith('/static/')) {
      const datos = await readFile(join(DIST, url.pathname.replace('/static/', '')))
      res.writeHead(200, { 'Content-Type': TIPOS[extname(url.pathname)] || 'application/octet-stream' })
      return res.end(datos)
    }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    res.end(shell(await activos(), url.searchParams))
  } catch (e) {
    res.writeHead(404, { 'Content-Type': 'text/plain' })
    res.end(`no encontrado: ${url.pathname} (${e.message})`)
  }
}).listen(PUERTO, () => console.log(`e2e server en http://localhost:${PUERTO}`))
