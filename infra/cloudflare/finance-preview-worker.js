/**
 * Cloudflare Worker — Funnel de Conquer Finance en www.conquerfinance.com
 * ──────────────────────────────────────────────────────────────────────────
 * Igual que preview-funnel-worker.js (blocks/legal) pero para la zona
 * conquerfinance.com, cuyo tráfico raíz sirve Webflow Y ESTÁ EN PRODUCCIÓN.
 * Por eso la prueba se hace bajo el prefijo /preview: solo se interceptan los
 * paths de las rutas asociadas al Worker; las URLs reales del funnel vivo
 * (clase-online-gratuita-latam, video-clase-latam, confirmacion-llamada…)
 * siguen en Webflow hasta el cutover final.
 *
 * Proxy "tonto": NO manipula el path. Reenvía tal cual (incluido /preview) al
 * origen Django, que ya sabe servir bajo /preview (AppBasePathMiddleware).
 *
 * DIFERENCIA CLAVE con blocks/legal: Finance resuelve la escuela por HOST
 * (FUNNEL_HOST_ESCUELA: conquerfinance.com → conquer-finance), no por el path.
 * Un Worker no puede reescribir el header Host de un fetch a otra zona, así
 * que mandamos X-Forwarded-Host con el host original; Django lo honra
 * (USE_X_FORWARDED_HOST=True en prod) y resuelve la escuela. El nginx del VPS
 * no pisa ese header (solo setea Host/X-Real-IP/X-Forwarded-For/Proto).
 * REQUISITO en prod: www.conquerfinance.com y conquerfinance.com deben estar
 * en CALENDARIO_ALLOWED_HOSTS, o Django responderá 400.
 *
 * RUTAS a asociar en la zona conquerfinance.com (fase de prueba /preview):
 *
 *   www.conquerfinance.com/preview/*   ← las páginas del funnel
 *   www.conquerfinance.com/static/*    ← JS/CSS (assets de Vite, root-relative)
 *   www.conquerfinance.com/f/*         ← API del funnel (/f/api/...)
 *   www.conquerfinance.com/media/*     ← imágenes subidas
 *
 * (/static, /f y /media no existen hoy en el Webflow de conquerfinance.com —
 * responden 404 — así que interceptarlos no toca ningún tráfico real.)
 *
 * CUTOVER final (cuando el preview esté validado): añadir las rutas reales y
 * quitar /preview/*. Mismo Worker, cero cambios de código:
 *
 *   www.conquerfinance.com/clase-online-gratuita-latam*
 *   www.conquerfinance.com/video-clase-latam*
 *   www.conquerfinance.com/confirmacion-llamada*
 *   www.conquerfinance.com/agenda/*
 *
 * Para revertir cualquier fase: borrar las rutas (o el Worker). Webflow vuelve
 * a recibir el 100% del tráfico al instante.
 */

const ORIGIN = "https://calendar.conquerx.com";

export default {
  async fetch(request) {
    const incoming = new URL(request.url);

    const target = new URL(ORIGIN);
    target.pathname = incoming.pathname; // sin tocar: incluye /preview, /static, /f, /media
    target.search = incoming.search;

    const headers = new Headers(request.headers);
    // Host original para que Django resuelva escuela=conquer-finance.
    headers.set("X-Forwarded-Host", incoming.host);
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
