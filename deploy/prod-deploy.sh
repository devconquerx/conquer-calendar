#!/usr/bin/env bash
#
# prod-deploy.sh — Despliegue AZUL/VERDE (zero downtime) de conquer-calendar.
# Corre EN EL SERVIDOR. Desde tu máquina usa ./deploy.sh (wrapper por SSH).
#
# ── Idea ─────────────────────────────────────────────────────────────────────
# Hay dos copias del front, `blue` (127.0.0.1:8001) y `green` (127.0.0.1:8002).
# Una sirve tráfico y la otra está parada. El despliegue levanta la parada con
# el código nuevo, la valida a fondo (health + smoke tests + SSR) MIENTRAS la
# vieja sigue sirviendo, y sólo entonces cambia el upstream de nginx y hace
# `reload`. La recarga de nginx es elegante: los workers viejos terminan los
# requests que ya tenían en vuelo antes de morir. Cero requests perdidos.
#
# Si algo falla ANTES del swap, no se toca nada: el color viejo nunca se enteró.
# Si algo falla DESPUÉS, se vuelve al color viejo (que sigue vivo) en ~1s.
#
# ── Subcomandos ──────────────────────────────────────────────────────────────
#   deploy          Despliegue completo (por defecto).
#   rollback        Vuelve al color anterior (sigue parado pero intacto).
#   status          Qué color sirve, con qué commit, salud de todo.
#   install-nginx   Instala/actualiza la config de nginx del host.
#   bootstrap       Migración única del esquema viejo (1 contenedor en :8000)
#                   al azul/verde, también sin caída.
#
# ── Variables de entorno ─────────────────────────────────────────────────────
#   DRAIN_SECONDS   25    Espera tras el swap antes de parar el color viejo.
#   HEALTH_TIMEOUT  180   Segundos máximos esperando a que el color nuevo esté sano.
#   FORCE           0     Salta la comprobación de "no redesplegar lo que falló".
#   SKIP_BUILD      0     Reusa la imagen ya construida (para pruebas).
#
set -Eeuo pipefail

# ─────────────────────────────── Config ──────────────────────────────────────
APP_DIR="${APP_DIR:-/home/conquer-calendar/app}"
STATE_DIR="${STATE_DIR:-/home/conquer-calendar/deploy}"
STATE_FILE="$STATE_DIR/state.env"
ACTIVE_COLOR_FILE="$STATE_DIR/active_color"   # lo lee el helper de cron
COMPOSE_FILE="${COMPOSE_FILE:-production.yml}"
UPSTREAM_FILE="${UPSTREAM_FILE:-/etc/nginx/conf.d/calendar-upstream.conf}"
SITE_AVAILABLE="/etc/nginx/sites-available/calendar.conquerx.com.conf"
SITE_ENABLED="/etc/nginx/sites-enabled/calendar.conquerx.com.conf"
DJANGO_IMAGE="conquer_calendario_production_django"
HEALTH_HOST="${HEALTH_HOST:-calendar.conquerx.com}"

DRAIN_SECONDS="${DRAIN_SECONDS:-25}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"
FORCE="${FORCE:-0}"
SKIP_BUILD="${SKIP_BUILD:-0}"

# Puertos por color (deben cuadrar con production.yml).
port_for() { case "$1" in blue) echo 8001 ;; green) echo 8002 ;; *) die "Color inválido: $1" ;; esac; }
other_color() { case "$1" in blue) echo green ;; green) echo blue ;; *) die "Color inválido: $1" ;; esac; }

# Smoke tests: "host|path|código esperado". Se piden DIRECTO al puerto del color
# nuevo (sin pasar por nginx), así que validan el color candidato sin que ningún
# usuario lo toque. Son GET de sólo lectura: no escriben nada en la BD.
SMOKE_TESTS=(
  "calendar.conquerx.com|/health/|200"
  "calendar.conquerx.com|/panel/|302"
  "calendar.conquerx.com|/conquer-blocks/clase-online-gratuita-latam/|200"
  "calendar.conquerx.com|/f/api/blocks-latam/config/|200"
  "calendar.conquerx.com|/conquer-legal/clase-online-gratuita-eu/|200"
  "www.conquerfinance.com|/clase-online-gratuita-latam|200"
)
# Página cuyo #funnel-root debe venir renderizado por el servicio SSR (está en
# FUNNEL_SSR_ALLOWLIST). Verifica de paso que el node-ssr del color nuevo vive.
SSR_HOST="calendar.conquerx.com"
SSR_PATH="/conquer-legal/clase-online-gratuita-eu/"

# ─────────────────────────────── Helpers ─────────────────────────────────────
c_blue=$'\033[1;34m'; c_grn=$'\033[1;32m'; c_red=$'\033[1;31m'; c_yel=$'\033[1;33m'; c_off=$'\033[0m'
say()  { echo "${c_blue}▶${c_off} $*"; }
ok()   { echo "${c_grn}✓${c_off} $*"; }
warn() { echo "${c_yel}!${c_off} $*"; }
die()  { echo "${c_red}✗ $*${c_off}" >&2; exit 1; }
trap 'echo "${c_red}✗ Falló en la línea $LINENO${c_off}" >&2' ERR

dc()  { docker compose -f "$COMPOSE_FILE" "$@"; }
dcc() { local color="$1"; shift; docker compose -f "$COMPOSE_FILE" --profile "$color" "$@"; }

cid_for() {  # $1=color $2=rol(django|node-ssr)
  docker ps -aq --filter "label=conquer.role=$2" --filter "label=conquer.color=$1" | head -1
}

# El color que sirve tráfico AHORA MISMO lo manda nginx, no un fichero nuestro:
# leemos el primer `server` sin `backup` del upstream. Así el estado real y el
# declarado no pueden divergir.
active_color_from_nginx() {
  [[ -f "$UPSTREAM_FILE" ]] || return 1
  local port
  port="$(grep -E '^[[:space:]]*server[[:space:]]+127\.0\.0\.1:[0-9]+' "$UPSTREAM_FILE" \
          | grep -v backup | head -1 | grep -oE '127\.0\.0\.1:[0-9]+' | cut -d: -f2)" || true
  case "$port" in
    8001) echo blue ;;
    8002) echo green ;;
    *) return 1 ;;
  esac
}

state_get() { [[ -f "$STATE_FILE" ]] && grep -E "^$1=" "$STATE_FILE" | tail -1 | cut -d= -f2- || true; }

state_write() {  # $1=color activo $2=sha activo $3=imagen activa $4=acción
  mkdir -p "$STATE_DIR"
  local standby prev_sha prev_img
  standby="$(other_color "$1")"
  prev_sha="$(state_get ACTIVE_SHA)"
  prev_img="$(state_get ACTIVE_IMAGE)"
  cat > "$STATE_FILE" <<EOF
# Generado por prod-deploy.sh — no editar a mano.
ACTIVE_COLOR=$1
ACTIVE_SHA=$2
ACTIVE_IMAGE=$3
STANDBY_COLOR=$standby
STANDBY_SHA=${prev_sha:-}
STANDBY_IMAGE=${prev_img:-}
LAST_ACTION=$4
UPDATED_AT=$(date +%FT%T%z)
EOF
  echo "$1" > "$ACTIVE_COLOR_FILE"
}

# ── nginx ────────────────────────────────────────────────────────────────────
write_upstream() {  # $1 = color que pasa a servir
  local active="$1" standby active_port standby_port
  standby="$(other_color "$active")"
  active_port="$(port_for "$active")"
  standby_port="$(port_for "$standby")"

  [[ -f "$UPSTREAM_FILE" ]] && cp -a "$UPSTREAM_FILE" "$UPSTREAM_FILE.bak"
  cat > "$UPSTREAM_FILE" <<EOF
# Generado por prod-deploy.sh el $(date +%FT%T%z). NO EDITAR A MANO.
# Color sirviendo: $active   (standby: $standby)
upstream calendar_app {
    server 127.0.0.1:${active_port} max_fails=0;          # activo  → $active
    server 127.0.0.1:${standby_port} max_fails=0 backup;  # standby → $standby
    keepalive 32;
}
EOF
  if ! nginx -t >/dev/null 2>&1; then
    [[ -f "$UPSTREAM_FILE.bak" ]] && mv "$UPSTREAM_FILE.bak" "$UPSTREAM_FILE"
    nginx -t || true
    die "nginx -t falló con el upstream nuevo; se restauró el anterior."
  fi
  # Recarga elegante: nginx arranca workers con la config nueva y los viejos
  # terminan sus requests en vuelo antes de salir. No se pierde ninguno.
  nginx -s reload
}

# ── Salud del color candidato ────────────────────────────────────────────────
wait_healthy() {  # $1=color
  local color="$1" cid status waited=0
  cid="$(cid_for "$color" django)"
  [[ -n "$cid" ]] || die "No existe contenedor django del color $color."
  say "Esperando a que $color esté healthy (máx ${HEALTH_TIMEOUT}s)…"
  while (( waited < HEALTH_TIMEOUT )); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo unknown)"
    [[ "$status" == "healthy" ]] && { ok "$color healthy tras ${waited}s."; return 0; }
    [[ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" == "true" ]] \
      || { docker logs --tail=40 "$cid" || true; die "El contenedor $color se murió al arrancar."; }
    sleep 3; waited=$((waited + 3))
  done
  docker logs --tail=40 "$cid" || true
  die "Timeout esperando salud de $color."
}

smoke() {  # $1=puerto
  local port="$1" host path expect code entry fail=0
  for entry in "${SMOKE_TESTS[@]}"; do
    IFS='|' read -r host path expect <<< "$entry"
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
            -H "Host: $host" "http://127.0.0.1:${port}${path}" || echo 000)"
    if [[ "$code" == "$expect" ]]; then
      echo "    ✓ $host$path → $code"
    else
      echo "    ✗ $host$path → $code (esperado $expect)"; fail=1
    fi
  done
  # El SSR debe rellenar #funnel-root; si el node-ssr del color nuevo no está,
  # Django cae a CSR y el div sale vacío (la página funciona, pero perdemos LCP
  # y SEO sin que nadie se entere: por eso lo tratamos como fallo del deploy).
  if curl -s --max-time 20 -H "Host: $SSR_HOST" "http://127.0.0.1:${port}${SSR_PATH}" \
       | tr -d '\n' | grep -q 'id="funnel-root"[^>]*><div'; then
    echo "    ✓ SSR renderizando (#funnel-root con contenido)"
  else
    echo "    ✗ SSR vacío: el node-ssr del color nuevo no responde"; fail=1
  fi
  return $fail
}

warmup() {  # $1=puerto — precalienta workers/plantillas/caché antes del swap
  local port="$1" entry host path
  for entry in "${SMOKE_TESTS[@]}"; do
    IFS='|' read -r host path _ <<< "$entry"
    for _ in 1 2 3; do
      curl -s -o /dev/null --max-time 20 -H "Host: $host" "http://127.0.0.1:${port}${path}" || true
    done
  done
}

json_field() {  # $1=json $2=campo → valor (string) o vacío
  printf '%s' "$1" | grep -oE "\"$2\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 | sed -E 's/.*"([^"]*)"$/\1/'
}

# La imagen lleva sellado el commit (ARG GIT_SHA → ENV DEPLOY_SHA) y /health/ lo
# devuelve junto al color. Así comprobamos que el contenedor que acabamos de
# levantar corre DE VERDAD el código nuevo, y no una imagen vieja que compose no
# llegó a adoptar (ha pasado con las imágenes tipo manifest-list de bake).
assert_version() {  # $1=color $2=puerto $3=sha esperado (vacío = no comprobar)
  local body sha color
  body="$(curl -s --max-time 15 -H "Host: $HEALTH_HOST" "http://127.0.0.1:$2/health/" || true)"
  sha="$(json_field "$body" sha)"
  color="$(json_field "$body" color)"
  [[ "$color" == "$1" ]] || die "El contenedor $1 responde color='$color'. Algo no cuadra: abortado sin tocar el tráfico."
  if [[ -n "$3" && "$sha" != "$3" ]]; then
    die "El color $1 sirve el commit '$sha' y esperábamos '$3': compose no adoptó la imagen nueva. Abortado sin tocar el tráfico."
  fi
  ok "Color $1 sirviendo el commit ${sha:-<sin sellar>}."
}

verify_through_nginx() {  # $1=puerto esperado $2=color esperado (opcional)
  local port="$1" color="${2:-}" out code upstream body served_color
  out="$(curl -sk --max-time 15 -D - -o /dev/null -H "Host: $HEALTH_HOST" "https://127.0.0.1/health/" || true)"
  code="$(printf '%s' "$out" | head -1 | awk '{print $2}')"
  upstream="$(printf '%s' "$out" | grep -i '^x-upstream:' | tr -d '\r' | awk '{print $2}')"
  [[ "$code" == "200" ]] || { warn "nginx devolvió $code en /health/"; return 1; }
  [[ "$upstream" == "127.0.0.1:$port" ]] || { warn "nginx sigue apuntando a $upstream (esperado 127.0.0.1:$port)"; return 1; }
  if [[ -n "$color" ]]; then
    body="$(curl -sk --max-time 15 -H "Host: $HEALTH_HOST" "https://127.0.0.1/health/" || true)"
    served_color="$(json_field "$body" color)"
    [[ "$served_color" == "$color" ]] || { warn "La URL pública responde color='$served_color' (esperado $color)"; return 1; }
  fi
  ok "nginx sirviendo desde $upstream (HTTP $code${color:+, color $color})."
}

preflight() {
  cd "$APP_DIR"
  command -v docker >/dev/null || die "docker no está instalado."
  dc config -q || die "$COMPOSE_FILE no es válido."
  nginx -t >/dev/null 2>&1 || die "La config de nginx actual ya está rota; arréglala antes de desplegar."
  [[ -f "$UPSTREAM_FILE" ]] || die "Falta $UPSTREAM_FILE. Corre primero: bash deploy/prod-deploy.sh bootstrap"

  local free_gb avail_mb
  free_gb="$(df -BG --output=avail / | tail -1 | tr -dc '0-9')"
  (( free_gb >= 8 )) || die "Sólo quedan ${free_gb}G libres en /; el build necesita margen."
  avail_mb="$(free -m | awk '/^Mem:/{print $7}')"
  (( avail_mb >= 800 )) || warn "Sólo ${avail_mb}MB de RAM disponible: el build del frontend va justo."
}

# ═══════════════════════════════ deploy ══════════════════════════════════════
cmd_deploy() {
  preflight
  local active new sha new_port img
  active="$(active_color_from_nginx)" || die "No pude determinar el color activo desde $UPSTREAM_FILE."
  new="$(other_color "$active")"
  new_port="$(port_for "$new")"
  sha="$(git rev-parse --short HEAD)"

  # Evita redesplegar a ciegas el commit que acabas de tumbar con un rollback.
  if [[ "$(state_get LAST_ACTION)" == "rollback" && "$(state_get ROLLED_BACK_SHA)" == "$sha" && "$FORCE" != "1" ]]; then
    die "El commit $sha es justo el que se revirtió en el último rollback. Corrige y vuelve a pushear (o FORCE=1)."
  fi

  echo "────────────────────────────────────────────"
  echo "  Activo ahora : $active ($(port_for "$active"))"
  echo "  Desplegando  : $new ($new_port)  ←  $sha"
  echo "────────────────────────────────────────────"

  # 1) Build. El color activo sigue sirviendo: aquí no hay ningún riesgo.
  export GIT_SHA="$sha"   # se sella dentro de la imagen y lo devuelve /health/
  if [[ "$SKIP_BUILD" == "1" ]]; then
    warn "SKIP_BUILD=1: se reutiliza la imagen existente."
  else
    say "Construyendo imágenes (frontend + django + node-ssr)…"
    dcc "$new" build "django-$new" "node-ssr-$new"
  fi

  # 2) Migraciones y estáticos one-off, con la imagen nueva y el color viejo aún
  #    sirviendo. Requiere migraciones compatibles hacia atrás (ver docs).
  say "Levantando Redis si hiciera falta…"
  dc up -d redis
  say "Aplicando migraciones…"
  dcc "$new" run --rm -T --no-deps "django-$new" python manage.py migrate --noinput </dev/null
  say "Recolectando estáticos…"
  # Los nombres llevan hash de contenido, así que los ficheros viejos siguen ahí
  # y las páginas ya servidas no se rompen a mitad del despliegue.
  dcc "$new" run --rm -T --no-deps "django-$new" python manage.py collectstatic --noinput </dev/null

  # 3) Arranca el color nuevo en su puerto (nadie le manda tráfico todavía).
  say "Arrancando el color $new…"
  dcc "$new" rm -sf "django-$new" "node-ssr-$new" >/dev/null 2>&1 || true
  dcc "$new" up -d "node-ssr-$new" "django-$new"
  wait_healthy "$new"
  if [[ "$SKIP_BUILD" == "1" ]]; then
    assert_version "$new" "$new_port" ""
  else
    assert_version "$new" "$new_port" "$sha"
  fi

  # 4) Validación real contra el color nuevo antes de darle un solo usuario.
  say "Smoke tests contra $new (puerto $new_port)…"
  if ! smoke "$new_port"; then
    docker logs --tail=60 "$(cid_for "$new" django)" || true
    dcc "$new" stop "django-$new" "node-ssr-$new" || true
    die "Smoke tests fallaron. NO se cambió el tráfico: sigue sirviendo $active."
  fi
  say "Precalentando workers…"
  warmup "$new_port"

  # 5) Celery a la versión nueva ANTES del swap: así el worker ya conoce las
  #    tareas nuevas cuando el Django nuevo empiece a encolarlas. El worker hace
  #    warm shutdown (termina lo que tiene en vuelo) y lo que llegue mientras
  #    tanto se queda encolado en Redis: no se pierde ninguna tarea.
  say "Reciclando Celery (worker + beat) a la imagen nueva…"
  dc stop -t 130 celeryworker celerybeat
  dc up -d celeryworker celerybeat

  # 6) EL SWAP. Recarga elegante de nginx: sin requests perdidos.
  say "Cambiando el tráfico a $new…"
  write_upstream "$new"
  sleep 1
  if ! verify_through_nginx "$new_port" "$new"; then
    warn "Verificación post-swap fallida → volviendo a $active."
    write_upstream "$active"
    die "Se revirtió el tráfico a $active. El color $new sigue arriba para que lo depures."
  fi

  img="$(docker inspect -f '{{.Image}}' "$(cid_for "$new" django)")"
  state_write "$new" "$sha" "$img" deploy

  # 7) Drenaje: damos margen a que los requests que aún estaban en el color
  #    viejo terminen, y sólo entonces lo paramos. Se queda PARADO (no borrado)
  #    para que `rollback` sea instantáneo.
  say "Drenando el color $active (${DRAIN_SECONDS}s)…"
  sleep "$DRAIN_SECONDS"
  dcc "$active" stop "django-$active" "node-ssr-$active"
  ok "Color $active parado (intacto para rollback)."

  docker image prune -f >/dev/null 2>&1 || true
  ok "Despliegue completado: $new @ $sha sirviendo. Rollback disponible → $active."
  cmd_status
}

# ═══════════════════════════════ rollback ════════════════════════════════════
cmd_rollback() {
  cd "$APP_DIR"
  local active old old_port old_img
  active="$(active_color_from_nginx)" || die "No pude determinar el color activo."
  old="$(other_color "$active")"
  old_port="$(port_for "$old")"

  [[ -n "$(cid_for "$old" django)" ]] || die "No queda contenedor del color $old: no hay a dónde volver."

  echo "────────────────────────────────────────────"
  echo "  Rollback: $active ($(state_get ACTIVE_SHA)) → $old ($(state_get STANDBY_SHA))"
  echo "────────────────────────────────────────────"

  say "Arrancando el color $old (tal cual quedó, con su imagen vieja)…"
  docker start "$(cid_for "$old" node-ssr)" >/dev/null 2>&1 || true
  docker start "$(cid_for "$old" django)" >/dev/null
  wait_healthy "$old"
  smoke "$old_port" || warn "Algún smoke test del color $old falla; se continúa igualmente (es el rollback)."

  # Celery vuelve también a la imagen vieja, si la tenemos registrada.
  old_img="$(state_get STANDBY_IMAGE)"
  if [[ -n "$old_img" ]] && docker image inspect "$old_img" >/dev/null 2>&1; then
    say "Devolviendo Celery a la imagen anterior…"
    docker tag "$old_img" "$DJANGO_IMAGE:latest"
    dc stop -t 130 celeryworker celerybeat
    dc up -d --force-recreate celeryworker celerybeat
  else
    warn "No hay imagen previa registrada: Celery se queda en la versión nueva."
  fi

  say "Devolviendo el tráfico a $old…"
  write_upstream "$old"
  verify_through_nginx "$old_port" "$old" || die "El swap de vuelta no verificó. REVISA YA."

  local rolled_back_sha
  rolled_back_sha="$(state_get ACTIVE_SHA)"
  state_write "$old" "$(state_get STANDBY_SHA)" "$old_img" rollback
  echo "ROLLED_BACK_SHA=$rolled_back_sha" >> "$STATE_FILE"

  say "Drenando ${DRAIN_SECONDS}s y parando $active…"
  sleep "$DRAIN_SECONDS"
  dcc "$active" stop "django-$active" "node-ssr-$active" || true
  ok "Rollback hecho: sirve $old."
  warn "OJO: el árbol de git del server sigue en el commit malo y las migraciones NO se revierten."
  warn "Arregla el código, pushea y vuelve a desplegar."
  cmd_status
}

# ═══════════════════════════════ status ══════════════════════════════════════
cmd_status() {
  cd "$APP_DIR"
  local active
  active="$(active_color_from_nginx || echo '?')"
  echo
  echo "── Estado ───────────────────────────────────"
  echo "  Sirviendo    : $active  (puerto $(port_for "$active" 2>/dev/null || echo '?'))"
  echo "  Commit activo: $(state_get ACTIVE_SHA)  ($(state_get UPDATED_AT))"
  echo "  Standby      : $(state_get STANDBY_COLOR) @ $(state_get STANDBY_SHA)"
  echo "  Árbol git    : $(git rev-parse --short HEAD) $(git log -1 --format=%s | cut -c1-60)"
  echo
  docker ps -a --filter "label=conquer.role" \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
  echo
  curl -sk -D - -o /dev/null --max-time 10 -H "Host: $HEALTH_HOST" https://127.0.0.1/health/ \
    | grep -iE '^(HTTP/|x-upstream)' | tr -d '\r' | sed 's/^/  /'
  echo "  body: $(curl -sk --max-time 10 -H "Host: $HEALTH_HOST" https://127.0.0.1/health/ || echo '(sin respuesta)')"
  echo "─────────────────────────────────────────────"
}

# ═══════════════════════════ install-nginx ═══════════════════════════════════
cmd_install_nginx() {
  cd "$APP_DIR"
  [[ -f deploy/nginx/calendar.conquerx.com.conf ]] || die "Falta deploy/nginx/calendar.conquerx.com.conf"
  say "Instalando config de nginx…"
  [[ -f "$SITE_AVAILABLE" ]] && cp -a "$SITE_AVAILABLE" "$SITE_AVAILABLE.bak.$(date +%s)"
  cp deploy/nginx/calendar.conquerx.com.conf "$SITE_AVAILABLE"
  ln -sf "$SITE_AVAILABLE" "$SITE_ENABLED"
  install -m 0755 deploy/bin/calendar-dj /usr/local/bin/calendar-dj
  nginx -t || die "nginx -t falló. Restaura desde $SITE_AVAILABLE.bak.*"
  nginx -s reload
  ok "nginx actualizado y helper /usr/local/bin/calendar-dj instalado."
}

# ═══════════════════════════════ bootstrap ═══════════════════════════════════
# Migración única desde el esquema viejo (un único contenedor app-django-1 en
# :8000) al azul/verde. También sin caída: se levanta blue en :8001, se apunta
# nginx allí y sólo después se retira el contenedor viejo.
cmd_bootstrap() {
  cd "$APP_DIR"
  local sha img legacy
  sha="$(git rev-parse --short HEAD)"
  legacy="$(docker ps -q --filter 'name=^app-django-1$' | head -1)"

  say "1/6 · Upstream de nginx apuntando al backend actual…"
  mkdir -p "$STATE_DIR"
  if [[ -n "$legacy" ]]; then
    # Paso puente: el upstream apunta al contenedor viejo (:8000) para poder
    # instalar ya la config nueva de nginx sin mover tráfico.
    cat > "$UPSTREAM_FILE" <<EOF
# Puente de bootstrap: backend legacy en :8000.
upstream calendar_app {
    server 127.0.0.1:8000 max_fails=0;
    keepalive 32;
}
EOF
  elif [[ -f "$UPSTREAM_FILE" ]]; then
    say "Ya hay upstream configurado; no se toca hasta validar el color nuevo."
  else
    # Sin backend legacy y sin upstream previo: no hay tráfico que preservar.
    write_upstream blue
  fi
  cmd_install_nginx
  verify_through_nginx "${legacy:+8000}" >/dev/null 2>&1 || true
  ok "nginx sirviendo a través del upstream."

  export GIT_SHA="$sha"
  say "2/6 · Construyendo imágenes del color blue…"
  dcc blue build django-blue node-ssr-blue

  say "3/6 · Migraciones + estáticos…"
  dc up -d redis
  dcc blue run --rm -T --no-deps django-blue python manage.py migrate --noinput </dev/null
  dcc blue run --rm -T --no-deps django-blue python manage.py collectstatic --noinput </dev/null

  say "4/6 · Levantando blue en :8001…"
  dcc blue up -d node-ssr-blue django-blue
  wait_healthy blue
  assert_version blue 8001 "$sha"
  smoke 8001 || die "blue no pasa los smoke tests; el backend viejo sigue sirviendo."

  say "5/6 · Cambiando el tráfico a blue…"
  write_upstream blue
  verify_through_nginx 8001 blue || die "El swap a blue no verificó."
  img="$(docker inspect -f '{{.Image}}' "$(cid_for blue django)")"
  state_write blue "$sha" "$img" bootstrap

  say "6/6 · Parando el backend viejo y reciclando Celery…"
  sleep "$DRAIN_SECONDS"
  if [[ -n "$legacy" ]]; then
    # Se PARA, no se borra. Si algo saliera mal después, `docker start
    # app-django-1` + apuntar el upstream a :8000 devuelve el servicio de antes
    # en segundos. Bórralo a mano (docker rm app-django-1) cuando el azul/verde
    # lleve unos días rodando.
    docker stop -t 45 app-django-1 >/dev/null
    ok "Contenedor legacy app-django-1 PARADO (no borrado: red de seguridad)."
  fi
  docker stop -t 15 app-node-ssr-1 >/dev/null 2>&1 || true
  dc stop -t 130 celeryworker celerybeat || true
  dc up -d celeryworker celerybeat

  ok "Bootstrap completado. A partir de ahora: ./deploy.sh"
  warn "Actualiza el crontab para que use /usr/local/bin/calendar-dj (ver docs/deploy-zero-downtime.md)."
  cmd_status
}

# ─────────────────────────────── Dispatch ────────────────────────────────────
case "${1:-deploy}" in
  deploy)         cmd_deploy ;;
  rollback)       cmd_rollback ;;
  status)         cmd_status ;;
  install-nginx)  cmd_install_nginx ;;
  bootstrap)      cmd_bootstrap ;;
  -h|--help|help) grep '^#' "$0" | sed 's/^# \{0,1\}//' ;;
  *) die "Subcomando desconocido: $1 (deploy|rollback|status|install-nginx|bootstrap)" ;;
esac
