# El banner de cookies en las páginas de Webflow

## El problema

El dominio de cada marca está partido en dos. Los embudos y las páginas de
evento las sirve esta aplicación; el resto lo sirve Webflow. El banner de
consentimiento propio vivía solo en las plantillas de Django, así que en la
mitad de Webflow seguía saliendo el de Cookiebot: otro diseño, otros textos y
—lo importante— otra decisión guardada. El mismo visitante podía tener que
aceptar dos veces.

## La solución

`/f/conquerx-cookies.js` devuelve el banner entero —estilos, marcado y
comportamiento— en un solo fichero. Webflow lo carga con una línea.

Sale de los mismos includes que usan las páginas de Django
(`_includes/_consentimiento_estilos.html` y `_consentimiento_markup.html`), así
que es literalmente el mismo banner y no hay dos que mantener.

## Qué pegar en Webflow

En **Project Settings → Custom Code → Head Code**, y **antes** del snippet de
GTM:

```html
<script src="https://www.conquerblocks.com/f/conquerx-cookies.js?marca=conquer-blocks"></script>
```

Una línea por sitio, cambiando el dominio y la marca:

| Sitio de Webflow | `marca` |
|---|---|
| conquerblocks.com | `conquer-blocks` |
| conquerfinance.com | `conquer-finance` |
| conquerlanguages.com | `conquer-languages` |
| conquerlegal.com | `conquer-legal` |

Tres cosas que no son opcionales:

- **Antes del snippet de GTM.** Los valores por defecto de Consent Mode tienen
  que estar puestos antes de que exista cualquier etiqueta de Google, o esa
  primera medición se escapa sin permiso.
- **Sin `async` ni `defer`**, por lo mismo. Todo lo que toca el DOM sí espera a
  que haya DOM, así que no bloquea el pintado.
- **`?marca=`**. El Worker de Cloudflare reescribe el Host (`PRESERVE_HOST =
  false`), así que Django ve `calendar.conquerx.com` y no puede deducir de qué
  marca es la página. Sin ese parámetro el banner sale con la paleta neutra —
  funciona, pero no es la de nadie. Cuando falta queda un WARNING en el log.

## Por qué desde el dominio de la marca y no desde calendar.conquerx.com

Porque por el camino se pierde el país del visitante. `X-Visitor-Country` la
pone el Worker de Cloudflare al enrutar los dominios de marca hacia Django; una
petición directa a `calendar.conquerx.com` no pasa por ahí. Y sin país el código
asume Europa: banner bloqueante en LATAM y en Estados Unidos, donde la ley no lo
pide.

No hace falta tocar Cloudflare: `/f/*` ya está enrutado en los cuatro dominios.

```bash
# Comprobado así (405 = la ruta llega a Django, solo que ese endpoint no acepta GET)
for d in www.conquerblocks.com www.conquerlanguages.com www.conquerfinance.com www.conquerlegal.com; do
  curl -s -o /dev/null -w "$d %{http_code}\n" "https://$d/f/api/blocks-latam/resolver/"
done
```

## Lo que sale gratis

La cookie `cqx_consent` es del dominio, no de la aplicación. Quien decide en una
página de Webflow llega al embudo con su decisión ya tomada, y al revés. No hay
nada que sincronizar.

## Cookiebot

Por defecto el bundle **impide que Cookiebot cargue**, igual que hacen las
plantillas de Django: lo inyecta el contenedor de GTM y, si se le deja, salen
dos banners.

Se le impide interceptando la asignación del `src`. Es un apaño y se nota. Lo
limpio es darle al tag de Cookiebot una excepción de trigger en cada contenedor;
el día que se haga, este bloque sobra en los dos sitios.

Para comparar cómo queda la página con el de Cookiebot, añade `&cookiebot=1` a
la URL del script.

## Depurar

| Parámetro | Para qué |
|---|---|
| `?debug=1` | Saca el banner aunque ya se haya decidido |
| `?marca=…` | Fuerza la marca |
| `&cookiebot=1` | Deja pasar Cookiebot |

Para ver el modo europeo desde fuera de Europa, la cabecera manda:

```bash
curl -s -H "X-Visitor-Country: ES" \
  "https://www.conquerblocks.com/f/conquerx-cookies.js?marca=conquer-blocks" | grep "var explicito"
```

## Qué se comprobó antes de darlo por bueno

- Las páginas de Django renderizan el banner igual que antes de partir el
  template en piezas: 12.408 → 12.410 bytes, dos líneas en blanco de los
  `include`. Nada funcional.
- En un navegador de verdad, sobre una página vacía que solo carga el script:
  el banner aparece con el color de la marca, «Aceptar todas» lo cierra, deja el
  icono flotante, guarda la cookie, y empuja al dataLayer los cuatro eventos que
  esperan los contenedores (`cookie_consent_preferences`, `_statistics`,
  `_marketing` y `_update`). Sin errores de JavaScript.
- Región: `ES` y `BR` piden permiso previo; `MX` y `US` informan sin bloquear.
- Quien ya decidió no vuelve a ver el banner, solo el icono, y el icono lo
  reabre.
