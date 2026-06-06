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
