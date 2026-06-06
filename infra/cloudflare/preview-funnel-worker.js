/**
 * Cloudflare Worker — Preview del funnel de Conquer en www.conquerblocks.com
 * ──────────────────────────────────────────────────────────────────────────
 * Objetivo: servir el funnel de Django (conquer-calendar) bajo el prefijo
 * /preview en www.conquerblocks.com, cuyo tráfico raíz sigue sirviéndolo
 * Webflow. Solo se interceptan los paths de las rutas asociadas a este Worker;
 * todo lo demás queda intacto en Webflow.
 *
 * Es un proxy "tonto": NO manipula el path. Reenvía la petición tal cual
 * (incluido el prefijo /preview) al origen Django. Django ya sabe servir bajo
 * /preview: AppBasePathMiddleware detecta el prefijo, lo retira para resolver
 * la ruta canónica y antepone /preview a las URLs de navegación que emite, de
 * modo que el flujo encadenado (landing → vídeo → stepform → confirmación)
 * permanece dentro de /preview.
 *
 * RUTAS que hay que asociar a este Worker en la zona conquerblocks.com
 * (Workers & Pages → tu Worker → Triggers → Routes):
 *
 *   www.conquerblocks.com/preview/*    ← las páginas del funnel
 *   www.conquerblocks.com/static/*     ← JS/CSS (assets de Vite, root-relative)
 *   www.conquerblocks.com/f/*          ← API del stepform (/f/api/...)
 *   www.conquerblocks.com/media/*      ← imágenes subidas
 *
 * Para revertir la prueba: borra estas 4 rutas (o el Worker). Webflow vuelve a
 * recibir el 100% del tráfico al instante.
 *
 * Nota sobre el Host: para conquer-blocks la escuela se resuelve por el PATH
 * (no por el dominio) y las APIs del funnel son csrf_exempt, así que reenviar
 * con Host = calendar.conquerx.com funciona sin cambios. Si en el futuro se
 * prueban languages/finance (que resuelven la escuela por Host), habría que
 * preservar el Host original — ver PRESERVE_HOST abajo.
 */

const ORIGIN = "https://calendar.conquerx.com";
const PRESERVE_HOST = false; // true → Django ve Host=www.conquerblocks.com

export default {
  async fetch(request) {
    const incoming = new URL(request.url);

    const target = new URL(ORIGIN);
    target.pathname = incoming.pathname; // sin tocar: incluye /preview, /static, /f, /media
    target.search = incoming.search;

    const headers = new Headers(request.headers);
    if (PRESERVE_HOST) {
      headers.set("Host", incoming.host);
      headers.set("X-Forwarded-Host", incoming.host);
    }
    headers.set("X-Forwarded-Proto", "https");

    const init = {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      // Los 301 de nginx (trailing slash) usan Location relativo, así que el
      // navegador re-entra por el Worker en el mismo host. Los dejamos pasar.
      redirect: "manual",
    };

    return fetch(target.toString(), init);
  },
};
