#!/usr/bin/env bash
#
# deploy.sh — Despliegue a producción de conquer-calendar.
#
# Modelo: TODO ocurre en el server. Localmente este script no compila, no
# commitea ni pushea: solo se conecta por SSH y despliega lo que ya esté en
# origin/<rama>. (Tú pusheas tu código con tu flujo normal de git.)
#
# Flujo en PROD (mínimo tiempo de caída):
#   git fetch + reset --hard a origin/<rama>
#   → docker build (la imagen compila el frontend con Node en una etapa de
#     build; el server NO necesita Node ni un dist commiteado)
#   → migraciones + collectstatic one-off con la imagen nueva
#   → swap rápido (up -d) → healthcheck
#   → ROLLBACK automático a la imagen previa si el healthcheck falla.
#
# Uso:
#   ./deploy.sh        # despliegue interactivo (pide confirmación)
#   sh deploy.sh       # también vale: se relanza solo con bash
#   ./deploy.sh -y     # sin confirmación
#
# Config por variables de entorno (con sus valores por defecto):
#   DEPLOY_SSH   root@167.172.146.251
#   REMOTE_DIR   /home/conquer-calendar/app
#   BRANCH       main
#   COMPOSE_FILE production.yml
#   SERVICE      django
#   IMAGE        conquer_calendario_production_django
#   HEALTH_HOST  calendar.conquerx.com
#

# Usa características de bash. Si lo invocan con `sh deploy.sh` (dash), se
# relanza a sí mismo con bash.
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -Eeuo pipefail

# ─────────────────────────── Config ───────────────────────────
DEPLOY_SSH="${DEPLOY_SSH:-root@167.172.146.251}"
REMOTE_DIR="${REMOTE_DIR:-/home/conquer-calendar/app}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
COMPOSE_FILE="${COMPOSE_FILE:-production.yml}"
SERVICE="${SERVICE:-django}"
IMAGE="${IMAGE:-conquer_calendario_production_django}"
HEALTH_HOST="${HEALTH_HOST:-calendar.conquerx.com}"
HEALTH_PATH="${HEALTH_PATH:-/health/}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"

AUTO_YES="${AUTO_YES:-0}"

# ─────────────────────────── Flags ────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)   AUTO_YES=1 ;;
    -h|--help)  grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Flag desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done

# ─────────────────────────── Helpers ──────────────────────────
c_blue=$'\033[1;34m'; c_grn=$'\033[1;32m'; c_red=$'\033[1;31m'; c_yel=$'\033[1;33m'; c_off=$'\033[0m'
log()  { echo "${c_blue}▶${c_off} $*"; }
ok()   { echo "${c_grn}✓${c_off} $*"; }
warn() { echo "${c_yel}!${c_off} $*"; }
die()  { echo "${c_red}✗ $*${c_off}" >&2; exit 1; }
trap 'die "Falló en la línea $LINENO."' ERR

confirm() {
  [[ "$AUTO_YES" == "1" ]] && return 0
  read -r -p "$1 [y/N] " ans
  [[ "$ans" =~ ^[yY]$ ]] || die "Cancelado por el usuario."
}

# ───────────────────── Confirmación ───────────────────────────
echo "────────────────────────────────────────────"
echo "  DESPLIEGUE A PRODUCCIÓN"
echo "  SSH     : $DEPLOY_SSH"
echo "  Dir     : $REMOTE_DIR"
echo "  Rama    : $REMOTE/$BRANCH (lo que esté pusheado)"
echo "  Compose : $COMPOSE_FILE"
echo "────────────────────────────────────────────"
warn "Se despliega lo que ya esté en $REMOTE/$BRANCH. Asegúrate de haber pusheado tus cambios."
confirm "¿Continuar con el despliegue a PROD?"

# ───────────────────── Fase REMOTA ────────────────────────────
log "Conectando a prod y desplegando…"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEPLOY_SSH" \
  "REMOTE='$REMOTE' BRANCH='$BRANCH' REMOTE_DIR='$REMOTE_DIR' COMPOSE_FILE='$COMPOSE_FILE' SERVICE='$SERVICE' IMAGE='$IMAGE' HEALTH_HOST='$HEALTH_HOST' HEALTH_PATH='$HEALTH_PATH' HEALTH_RETRIES='$HEALTH_RETRIES' bash -s" <<'REMOTE'
set -Eeuo pipefail
say() { echo "  [prod] $*"; }

cd "$REMOTE_DIR"
dc() { docker compose -f "$COMPOSE_FILE" "$@"; }

say "Actualizando código (reset duro a $REMOTE/$BRANCH)…"
git fetch "$REMOTE" "$BRANCH"
git checkout "$BRANCH"
git reset --hard "$REMOTE/$BRANCH"
say "Código en: $(git rev-parse --short HEAD)"

# Imagen actual (para rollback). Puede estar vacío en el primer deploy.
PREV_IMG_ID="$(docker images -q "$IMAGE" | head -1 || true)"
say "Imagen previa: ${PREV_IMG_ID:-<ninguna>}"

# 1) Build de la nueva imagen (compila el frontend con Node + instala deps de
#    prod). El contenedor viejo sigue corriendo → SIN downtime en esta etapa.
say "Construyendo imagen nueva (incluye build del frontend)…"
dc build

# 2) Migraciones + estáticos one-off con la imagen nueva, mientras el viejo
#    sigue sirviendo.
say "Aplicando migraciones…"
dc run --rm "$SERVICE" python manage.py migrate --noinput
say "Recolectando estáticos…"
dc run --rm "$SERVICE" python manage.py collectstatic --noinput

# 3) Swap rápido a los contenedores nuevos (única ventana de caída, ~segundos).
say "Reiniciando contenedores…"
dc up -d --remove-orphans

# 4) Healthcheck
say "Verificando salud…"
healthy=0
for i in $(seq 1 "$HEALTH_RETRIES"); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $HEALTH_HOST" "http://127.0.0.1:8000${HEALTH_PATH}" || true)"
  if [ "$code" = "200" ]; then healthy=1; break; fi
  sleep 2
done

if [ "$healthy" != "1" ]; then
  say "✗ HEALTHCHECK FALLÓ (último código: ${code:-n/a})."
  if [ -n "$PREV_IMG_ID" ]; then
    say "Haciendo ROLLBACK a la imagen previa ($PREV_IMG_ID)…"
    docker tag "$PREV_IMG_ID" "$IMAGE"
    dc up -d --remove-orphans
    say "Rollback aplicado. Revisa los logs:"
  fi
  dc logs --tail=60 "$SERVICE" || true
  exit 1
fi

say "✓ Healthcheck OK."
docker image prune -f >/dev/null 2>&1 || true
say "✓ Despliegue completado."
REMOTE

ok "Despliegue a producción finalizado correctamente."
