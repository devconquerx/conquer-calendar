# Preview del funnel en www.conquerblocks.com (Cloudflare)

Prueba para servir el funnel de Django bajo `/preview` en `www.conquerblocks.com`
(cuyo tráfico raíz lo sirve Webflow), sin tocar las páginas reales. Permite
validar que Cloudflare puede interceptar un path y procesarlo con Django.

## Cómo funciona

- **Cloudflare Worker** (`preview-funnel-worker.js`): proxy tonto. Reenvía los
  paths de sus rutas a `calendar.conquerx.com` sin modificar el path.
- **Django** (`AppBasePathMiddleware` + `FUNNEL_BASE_PATHS=/preview`): detecta el
  prefijo `/preview`, lo retira para resolver la ruta canónica y antepone
  `/preview` a las URLs de navegación que emite. Así el flujo encadenado se
  queda dentro de `/preview`. Sin prefijo (calendar.conquerx.com) no cambia nada.

## Orden de despliegue

1. **Django a prod primero.** Desde el repo: `./deploy.sh` (despliega `main`).
   El código del funnel + soporte `/preview` debe estar en prod ANTES de montar
   Cloudflare; si no, el origen responde 404.
2. **Verificar el origen** (sin Cloudflare de por medio):

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" \
     https://calendar.conquerx.com/preview/conquer-blocks/clase-online-gratuita-latam/
   # Esperado: 200  (si 404 → falta el FunnelForm activo de conquer-blocks/latam en la BD de prod)
   ```

3. **Crear el Worker** en el dashboard de Cloudflare (zona `conquerblocks.com`),
   pegar el contenido de `preview-funnel-worker.js`, y asociar las 4 rutas:

   ```
   www.conquerblocks.com/preview/*
   www.conquerblocks.com/static/*
   www.conquerblocks.com/f/*
   www.conquerblocks.com/media/*
   ```

4. **Probar** en el navegador:
   `https://www.conquerblocks.com/preview/conquer-blocks/clase-online-gratuita-latam`

   La página real `https://www.conquerblocks.com/conquer-blocks/clase-online-gratuita-latam`
   (sin `/preview`) sigue intacta en Webflow.

## Requisitos en prod

- `calendar.conquerx.com` accesible públicamente (lo está).
- Existe un `FunnelForm` activo para `escuela=conquer-blocks`, `region=latam`.
- `CALENDARIO_FUNNEL_BASE_PATHS` por defecto es `/preview` (no hace falta tocar
  nada salvo que se quiera otro prefijo o desactivarlo dejándolo vacío).

## Revertir

Borra las 4 rutas (o el Worker). Webflow recupera el 100% del tráfico al instante.
Ningún cambio de Django afecta el comportamiento sin prefijo.

---

# Preview del funnel en www.conquerfinance.com (dominio VIVO)

Igual que arriba pero para Conquer Finance, con DOS diferencias importantes:

1. **El dominio está en producción** (Webflow sirve el funnel real que convierte
   hoy). Por eso la prueba va bajo `/preview/*`: las URLs reales
   (`/clase-online-gratuita-latam`, `/video-clase-latam`, `/confirmacion-llamada`)
   no se tocan hasta el cutover final.
2. **Finance resuelve la escuela por HOST** (no por path, como blocks/legal), así
   que el Worker es otro (`finance-preview-worker.js`): reenvía
   `X-Forwarded-Host: www.conquerfinance.com` y Django lo honra
   (`USE_X_FORWARDED_HOST=True`). El nginx del VPS no pisa ese header.

Las URLs que emite Django para finance son **idénticas carácter a carácter** a
las de producción (sin barra final; confirmación compartida sin sufijo de
región): en el cutover no cambia ninguna URL. Paths añadidos que no existían en
prod LATAM: `/agenda/proptrading/latam/` (stepform; sigue la convención que
finance ya usaba en EU) y el flujo de prellamada dentro del SPA.

## Orden de despliegue

1. **Django a prod** (`./deploy.sh` desde el repo, despliega `main`).
2. **ALLOWED_HOSTS**: en el VPS (167.172.146.251), editar
   `/home/conquer-calendar/.env` (ojo: el env_file de los servicios es ese, NO
   `app/.env`) y añadir los dominios de finance:

   ```
   CALENDARIO_ALLOWED_HOSTS=167.172.146.251,calendar.conquerx.com,www.conquerfinance.com,conquerfinance.com
   CALENDARIO_CSRF_TRUSTED_ORIGINS=https://calendar.conquerx.com,http://167.172.146.251,https://www.conquerfinance.com
   ```

   y reciclar: `cd /home/conquer-calendar/app && docker compose -f production.yml up -d django`.
3. **Verificar el origen** simulando lo que mandará el Worker:

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" \
     -H 'X-Forwarded-Host: www.conquerfinance.com' \
     https://calendar.conquerx.com/preview/clase-online-gratuita-latam
   # Esperado: 200 (400 → falta ALLOWED_HOSTS; 404 → falta el FunnelForm activo
   # de conquer-finance/latam en la BD de prod)
   ```

4. **Crear el Worker** `conquerfinance-preview-funnel` en el dashboard (misma
   cuenta; las rutas se asocian en la zona `conquerfinance.com`), pegar
   `finance-preview-worker.js` y asociar las rutas:

   ```
   www.conquerfinance.com/preview/*
   www.conquerfinance.com/static/*
   www.conquerfinance.com/f/*
   www.conquerfinance.com/media/*
   ```

   Verificado (2026-07-29): `/static/*`, `/f/*` y `/media/*` hoy responden 404
   en el Webflow de conquerfinance.com (no hay tráfico real en esos paths), así
   que interceptarlos es inocuo. `/f/*` es además redundante en la práctica: el
   bundle de prod hornea `VITE_CALENDAR_ORIGIN=https://calendar.conquerx.com` y
   las llamadas de API van directas a ese origen (CORS abierto), pero la ruta
   cubre cualquier request root-relative que quede.

5. **Probar el funnel completo** en el dominio real:
   `https://www.conquerfinance.com/preview/clase-online-gratuita-latam`
   → vídeo → stepform → calendario nativo → `/preview/confirmacion-llamada`.

   BONUS: al correr en el dominio registrado, Cookiebot muestra el banner y,
   tras aceptar, GA4/Meta disparan de verdad (imposible desde localhost). OJO:
   las conversiones de las pruebas son REALES para GTM/Ads — usar emails de
   test reconocibles.

## Cutover final (cuando el preview esté validado)

En la zona `conquerfinance.com`, añadir al MISMO Worker las rutas reales:

```
www.conquerfinance.com/clase-online-gratuita-latam*
www.conquerfinance.com/video-clase-latam*
www.conquerfinance.com/confirmacion-llamada*
www.conquerfinance.com/agenda/*
```

(y opcionalmente quitar `/preview/*`). Sin cambios de código ni de URLs: Django
ya sirve esos paths en la raíz. Para revertir cualquier fase, borrar las rutas —
Webflow recupera el tráfico al instante.
