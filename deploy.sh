#!/usr/bin/env bash
#
# deploy.sh — Despliegue a producción de conquer-calendar desde local.
#
# Flujo (mínimo tiempo de caída):
#   LOCAL : compila el frontend (Vite), commitea dist + código, push a la rama.
#   PROD  : git reset a origin/<rama> → build de la imagen (sin downtime, el
#           contenedor viejo sigue sirviendo) → migraciones y collectstatic
#           one-off con la imagen nueva → swap rápido (up -d) → healthcheck.
#           Si el healthcheck falla, hace ROLLBACK automático a la imagen previa.
#
# Prod NO tiene Node: el frontend se compila aquí y el dist va commiteado.
#
# Uso:
#   ./deploy.sh                 # despliegue interactivo (pide confirmación)
#   sh deploy.sh                # también vale: se relanza solo con bash
#   ./deploy.sh -y              # sin confirmación
#   ./deploy.sh --no-frontend   # no recompila el frontend (usa el dist actual)
#   ./deploy.sh -m "mensaje"    # mensaje de commit personalizado
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

# El script usa características de bash (pipefail, [[ ]], trap ERR). Si lo
# invocan con `sh deploy.sh` (dash), se relanza a sí mismo con bash.
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
FRONTEND_DIR="frontend"

AUTO_YES="${AUTO_YES:-0}"
DO_FRONTEND=1
COMMIT_MSG=""

# ─────────────────────────── Flags ────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)         AUTO_YES=1 ;;
    --no-frontend)    DO_FRONTEND=0 ;;
    -m|--message)     shift; COMMIT_MSG="${1:-}" ;;
    -h|--help)        grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Flag desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done
COMMIT_MSG="${COMMIT_MSG:-deploy: $(date +%Y-%m-%d_%H-%M-%S)}"

# ─────────────────────────── Helpers ──────────────────────────
c_blue=$'\033[1;34m'; c_grn=$'\033[1;32m'; c_red=$'\033[1;31m'; c_yel=$'\033[1;33m'; c_off=$'\033[0m'
log()  { echo "${c_blue}▶${c_off} $*"; }
ok()   { echo "${c_grn}✓${c_off} $*"; }
warn() { echo "${c_yel}!${c_off} $*"; }
die()  { echo "${c_red}✗ $*${c_off}" >&2; exit 1; }
trap 'die "Falló en la línea $LINENO. Prod NO fue modificado si el fallo fue en la fase local/build."' ERR

confirm() {
  [[ "$AUTO_YES" == "1" ]] && return 0
  read -r -p "$1 [y/N] " ans
  [[ "$ans" =~ ^[yY]$ ]] || die "Cancelado por el usuario."
}

# Raíz del repo (donde está este script)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ───────────────────── Fase LOCAL: validaciones ────────────────
log "Validando estado local…"
command -v git >/dev/null || die "git no está instalado."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "No es un repo git."

CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[[ "$CUR_BRANCH" == "$BRANCH" ]] || die "Estás en '$CUR_BRANCH' pero se despliega '$BRANCH'. Haz checkout/merge a '$BRANCH' primero (o exporta BRANCH=$CUR_BRANCH)."

# ───────────────────── Fase LOCAL: build frontend ─────────────
if [[ "$DO_FRONTEND" == "1" ]]; then
  command -v npm >/dev/null || die "npm no está instalado (necesario para compilar el frontend)."
  log "Compilando frontend (Vite)…"
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    log "Instalando dependencias del frontend (npm ci)…"
    ( cd "$FRONTEND_DIR" && npm ci )
  fi
  ( cd "$FRONTEND_DIR" && npm run build )
  ok "Frontend compilado."
else
  warn "Saltando build del frontend (--no-frontend). Se usará el dist actual."
fi

# ───────────────────── Fase LOCAL: commit + push ──────────────
log "Preparando commit (código + dist compilado)…"
git add -u                                  # cambios de archivos YA versionados
git add -f "$FRONTEND_DIR/dist"             # dist está en .gitignore: se fuerza

if git diff --cached --quiet; then
  warn "No hay cambios nuevos para commitear."
else
  git commit -m "$COMMIT_MSG"
  ok "Commit creado: $COMMIT_MSG"
fi

log "Push a $REMOTE/$BRANCH…"
git push "$REMOTE" "$BRANCH"
LOCAL_SHA="$(git rev-parse --short HEAD)"
ok "Push hecho (HEAD=$LOCAL_SHA)."

# ───────────────────── Confirmación de PROD ───────────────────
echo
echo "────────────────────────────────────────────"
echo "  DESPLIEGUE A PRODUCCIÓN"
echo "  SSH     : $DEPLOY_SSH"
echo "  Dir     : $REMOTE_DIR"
echo "  Rama    : $BRANCH  →  $LOCAL_SHA"
echo "  Compose : $COMPOSE_FILE ($SERVICE)"
echo "────────────────────────────────────────────"
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

# 1) Build de la nueva imagen (instala deps de prod). El contenedor viejo
#    sigue corriendo → SIN downtime durante esta etapa (la más larga).
say "Construyendo imagen nueva…"
dc build "$SERVICE"

# 2) Migraciones + estáticos one-off con la imagen nueva, mientras el viejo
#    sigue sirviendo. Así el arranque del contenedor nuevo es casi instantáneo.
say "Aplicando migraciones…"
dc run --rm "$SERVICE" python manage.py migrate --noinput
say "Recolectando estáticos…"
dc run --rm "$SERVICE" python manage.py collectstatic --noinput

# 3) Swap rápido al contenedor nuevo (única ventana de caída, ~segundos).
say "Reiniciando contenedor…"
dc up -d "$SERVICE"

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
    dc up -d "$SERVICE"
    say "Rollback aplicado. Revisa los logs:"
  fi
  dc logs --tail=60 "$SERVICE" || true
  exit 1
fi

say "✓ Healthcheck OK."
# Limpieza de imágenes colgantes (no toca la previa si hubo rollback porque salimos antes).
docker image prune -f >/dev/null 2>&1 || true
say "✓ Despliegue completado."
REMOTE

ok "Despliegue a producción finalizado correctamente."
