# Despliegue sin caída (azul/verde)

## El problema que resuelve

El deploy anterior paraba y recreaba el contenedor de Django (`docker compose rm
-sf django && up -d`). Entre la parada y el primer request servido pasaba ~1
minuto: `/start` corría `migrate` y `collectstatic` (los assets de Metronic
tardan ~30s) y sólo después arrancaba gunicorn. Durante esa ventana nginx no
tenía a quién proxear y devolvía **502 a todo el mundo**.

No era teórico. En un solo día (19-ago-2026), con 9 ventanas de despliegue:

```
519 requests con 502/504, entre ellos:
   42  POST /f/api/video-progress/
   27  GET  /conquer-blocks/clase-online-gratuita-latam?...gclid=...   ← tráfico de pago
   18  POST /webhooks/google-calendar/
   12  POST /f/api/blocks-latam/resolver/
    7  POST /f/api/lead/                                              ← leads perdidos
```

## Cómo funciona ahora

Hay **dos copias completas del front**, `blue` y `green`, cada una con su Django
y su servicio SSR propio. Sólo una recibe tráfico; la otra está parada.

```
                    ┌──────────────────────────────────────┐
   Internet ──443──▶│ nginx (host)                         │
                    │  /static/, /media/ → disco (siempre)  │
                    │  /            → upstream calendar_app │
                    └───────────────┬──────────────────────┘
                                    │
                 /etc/nginx/conf.d/calendar-upstream.conf
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼ activo                                     ▼ backup/standby
     127.0.0.1:8001  django-blue                  127.0.0.1:8002  django-green
                     └─ node-ssr-blue                              └─ node-ssr-green

     (sin color, compartidos): celeryworker · celerybeat · redis
```

El despliegue levanta el color **parado** con el código nuevo, lo valida a fondo
mientras el otro sigue sirviendo, y sólo entonces reescribe el upstream y hace
`nginx -s reload`. La recarga de nginx es *elegante*: los workers viejos
terminan los requests que ya tenían en vuelo antes de morir y los nuevos entran
por el color nuevo. **Ningún request se pierde ni se corta.**

Secuencia exacta (`deploy/prod-deploy.sh deploy`):

| # | Paso | ¿Riesgo para el tráfico? |
|---|------|--------------------------|
| 1 | `git pull` + `docker build` (frontend + django + ssr) | Ninguno: el color activo ni se entera |
| 2 | `migrate` + `collectstatic` one-off con la imagen nueva | Ninguno (ver *Migraciones* abajo) |
| 3 | Arranca el color standby en su puerto | Ninguno: nadie le manda tráfico |
| 4 | Espera `healthy` + smoke tests + verificación de SSR | Si falla, **se aborta y no se tocó nada** |
| 5 | Celery worker/beat pasan a la imagen nueva (warm shutdown) | Las tareas se encolan en Redis, no se pierden |
| 6 | **Swap**: reescribe el upstream + `nginx -s reload` | Cero requests perdidos |
| 7 | Verifica a través de nginx (`X-Upstream`) | Si falla, vuelve solo al color viejo |
| 8 | Drenaje (25s) y parada del color viejo | El color viejo queda intacto para rollback |

## Uso diario

```bash
./deploy.sh              # desplegar lo que esté en origin/main
./deploy.sh -y           # sin confirmación
./deploy.sh --status     # qué color y qué commit están sirviendo
./deploy.sh --rollback   # volver al color anterior (~segundos)
```

En el servidor (equivalente, si prefieres entrar por SSH):

```bash
cd /home/conquer-calendar/app
bash deploy/prod-deploy.sh status|deploy|rollback
```

### Rollback

`./deploy.sh --rollback` arranca el color anterior (que quedó parado pero
intacto, con **su** imagen), lo valida, devuelve Celery a la imagen previa y
cambia el upstream. Tarda segundos y no reconstruye nada.

Lo que **no** deshace: las migraciones ya aplicadas y el `collectstatic`. Por eso
las migraciones tienen que ser compatibles hacia atrás (siguiente sección).
Después de un rollback, el árbol de git del servidor sigue en el commit malo:
arregla el código, pushea y despliega de nuevo (el script se niega a
redesplegar el commit revertido salvo `FORCE=1`).

## Migraciones: la única regla que hay que respetar

Con azul/verde, **el código viejo y el nuevo conviven contra la misma base de
datos** durante el despliegue (y durante todo el tiempo que dure un rollback).
Las migraciones se aplican antes del swap, así que el código viejo tiene que
seguir funcionando con el esquema nuevo.

Seguro en un solo despliegue (aditivo):

- Añadir una tabla o un modelo.
- Añadir una columna **nullable** o con `default`.
- Añadir un índice (`CONCURRENTLY` si la tabla es grande).
- Añadir un valor nuevo a un `choices`.

Requiere **dos despliegues** (expand → contract):

| Quiero… | Despliegue 1 | Despliegue 2 |
|---|---|---|
| Borrar una columna | Dejar de leerla/escribirla en el código | La migración que la borra |
| Renombrar una columna | Añadir la nueva + escribir en ambas | Migrar datos, borrar la vieja |
| Poner `NOT NULL` | Rellenar los nulos + empezar a escribir siempre | Añadir la restricción |
| Renombrar/borrar una tarea de Celery | Dejar de encolarla | Borrar la tarea |

Si una migración no puede ser compatible, díselo al script: despliega en
horario de bajo tráfico y asume que el rollback no será posible sin tocar la BD
a mano.

## Cambios que trajo esto

- `production.yml`: servicios `django-blue`/`django-green` y
  `node-ssr-blue`/`node-ssr-green` con *profiles* de compose, puertos 8001/8002
  y `stop_grace_period` (45s Django, 130s el worker de Celery, para que ni un
  request ni una tarea mueran por SIGKILL).
- `compose/production/django/start`: **ya no** corre `migrate` ni
  `collectstatic` (lo hace el deploy, one-off) y gunicorn arranca con
  `--graceful-timeout 30`.
- `deploy/nginx/calendar.conquerx.com.conf`: proxy al upstream `calendar_app`
  con keepalive y `proxy_next_upstream` (si el color activo no acepta la
  conexión, nginx reintenta en el standby; los POST ya enviados nunca se
  reintentan, así que un lead no se procesa dos veces).
- `deploy/bin/calendar-dj`: helper para el cron, porque el contenedor ya no se
  llama `app-django-1`.

### ⚠️ El crontab hay que actualizarlo

Los cron jobs hacían `docker exec app-django-1 …`, un nombre que ya no existe.
Tras el bootstrap, `crontab -e` en el servidor y dejarlo así:

```cron
*/10 * * * * /usr/local/bin/calendar-dj python manage.py sync_gcal_incremental --todos >> /var/log/gcal_incremental.log 2>&1
0 3 */5 * * /usr/local/bin/calendar-dj python manage.py renovar_canales_gcal --margen-horas 48 >> /var/log/gcal_renovar.log 2>&1
*/5 * * * * /usr/local/bin/calendar-dj python manage.py enviar_recordatorios >> /var/log/recordatorios.log 2>&1
```

## Puesta en marcha (una sola vez)

`./deploy.sh --bootstrap` migra del esquema viejo (un contenedor en :8000) al
azul/verde **también sin caída**: instala la config de nginx apuntando al
backend actual, levanta `blue` en :8001, lo valida, cambia el upstream y sólo
entonces retira el contenedor viejo.

Después: actualizar el crontab (arriba) y comprobar `./deploy.sh --status`.

## Diagnóstico

```bash
./deploy.sh --status                  # color activo, commit, salud, X-Upstream
ssh root@167.172.146.251 'docker ps -a --filter label=conquer.role'
ssh root@167.172.146.251 'cat /etc/nginx/conf.d/calendar-upstream.conf'
ssh root@167.172.146.251 'cat /home/conquer-calendar/deploy/state.env'
# ¿Quedan 502 después de un despliegue? (deberían ser 0)
ssh root@167.172.146.251 'grep -cE " (502|504) " /var/log/nginx/access.log'
```

Un despliegue **nunca** debe dejar 502 nuevos en el log. Si aparecen, algo del
swap no funcionó: revísalo antes del siguiente despliegue.

## Qué NO cubre

- **Caída del servidor entero** (un solo VPS): esto elimina la caída *del
  despliegue*, no da alta disponibilidad.
- **Migraciones destructivas**: ver la regla de arriba.
- **Requests de más de ~45s**: el drenaje son 25s + 45s de gracia; súbelos con
  `DRAIN_SECONDS` si algún día hay endpoints más lentos.
