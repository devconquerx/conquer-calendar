// Config de Vite para worktrees de Superset: hereda la del equipo (vite.config.js)
// pero usa un puerto propio (VITE_PORT) para port/origin/hmr, evitando la colisión
// en 5173 cuando hay varios worktrees corriendo Vite a la vez.
//
// La copia .superset/worktree-setup.sh dentro de cada worktree (archivo local).
// El preset 🐳 Up la usa: npm run dev -- --config vite.config.superset.mjs
import base from './vite.config.js'

const port = Number(process.env.VITE_PORT) || 5173

export default {
  ...base,
  server: {
    ...(base.server || {}),
    port,
    strictPort: true,
    origin: `http://localhost:${port}`,
    hmr: { ...((base.server && base.server.hmr) || {}), host: 'localhost', port, protocol: 'ws' },
  },
}
