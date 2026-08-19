#!/usr/bin/env bash
#
# deploy.sh — Despliegue a producción de conquer-calendar, SIN CAÍDA.
#
# Este script es sólo el mando a distancia: se conecta por SSH, actualiza el
# código a lo que ya esté en origin/<rama> y lanza deploy/prod-deploy.sh, que es
# quien orquesta el despliegue azul/verde en el servidor.
#
# Qué pasa allí (detalle completo en docs/deploy-zero-downtime.md):
#   1. build de la imagen nueva  → el color que sirve ni se entera
#   2. migraciones + collectstatic one-off
#   3. arranca el color STANDBY con el código nuevo (nadie le manda tráfico)
#   4. health + smoke tests + SSR contra ese color; si falla, se aborta y NO se
#      ha tocado el tráfico
#   5. Celery pasa a la versión nueva (warm shutdown: no pierde tareas)
#   6. nginx cambia de upstream con `reload` → los requests en vuelo terminan en
#      el color viejo y los nuevos entran en el nuevo: CERO requests perdidos
#   7. drenaje y parada del color viejo (queda intacto para rollback en ~1s)
#
# Uso:
#   ./deploy.sh              # despliegue (pide confirmación)
#   ./deploy.sh -y           # sin confirmación
#   ./deploy.sh --status     # qué color/commit está sirviendo
#   ./deploy.sh --rollback   # vuelve al color anterior (instantáneo)
#   ./deploy.sh --bootstrap  # migración única al esquema azul/verde
#
# Config por variables de entorno (con sus valores por defecto):
#   DEPLOY_SSH     root@167.172.146.251
#   REMOTE_DIR     /home/conquer-calendar/app
#   BRANCH         main
#   DRAIN_SECONDS  25    (se pasa al servidor)
#   FORCE          0     (se pasa al servidor)
#

if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -Eeuo pipefail

DEPLOY_SSH="${DEPLOY_SSH:-root@167.172.146.251}"
REMOTE_DIR="${REMOTE_DIR:-/home/conquer-calendar/app}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
AUTO_YES="${AUTO_YES:-0}"
ACTION="deploy"

c_blue=$'\033[1;34m'; c_grn=$'\033[1;32m'; c_red=$'\033[1;31m'; c_yel=$'\033[1;33m'; c_off=$'\033[0m'
log()  { echo "${c_blue}▶${c_off} $*"; }
ok()   { echo "${c_grn}✓${c_off} $*"; }
warn() { echo "${c_yel}!${c_off} $*"; }
die()  { echo "${c_red}✗ $*${c_off}" >&2; exit 1; }
trap 'die "Falló en la línea $LINENO."' ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)        AUTO_YES=1 ;;
    --status)        ACTION="status" ;;
    --rollback)      ACTION="rollback" ;;
    --bootstrap)     ACTION="bootstrap" ;;
    --install-nginx) ACTION="install-nginx" ;;
    -h|--help)       grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Flag desconocido: $1" >&2; exit 2 ;;
  esac
  shift
done

confirm() {
  [[ "$AUTO_YES" == "1" ]] && return 0
  read -r -p "$1 [y/N] " ans
  [[ "$ans" =~ ^[yY]$ ]] || die "Cancelado por el usuario."
}

# Variables que se propagan al script remoto.
REMOTE_ENV="DRAIN_SECONDS='${DRAIN_SECONDS:-25}' HEALTH_TIMEOUT='${HEALTH_TIMEOUT:-180}' FORCE='${FORCE:-0}' SKIP_BUILD='${SKIP_BUILD:-0}'"

# `status` no toca nada: ni confirmación ni git pull.
if [[ "$ACTION" == "status" ]]; then
  exec ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEPLOY_SSH" \
    "cd '$REMOTE_DIR' && bash deploy/prod-deploy.sh status"
fi

if [[ "$ACTION" == "rollback" ]]; then
  warn "Vas a devolver el tráfico al color ANTERIOR (el código de antes del último despliegue)."
  warn "Las migraciones NO se revierten."
  confirm "¿Hacer rollback en PROD?"
  exec ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEPLOY_SSH" \
    "cd '$REMOTE_DIR' && $REMOTE_ENV bash deploy/prod-deploy.sh rollback"
fi

echo "────────────────────────────────────────────"
echo "  DESPLIEGUE A PRODUCCIÓN (azul/verde, sin caída)"
echo "  SSH     : $DEPLOY_SSH"
echo "  Dir     : $REMOTE_DIR"
echo "  Rama    : $REMOTE/$BRANCH (lo que esté pusheado)"
echo "  Acción  : $ACTION"
echo "────────────────────────────────────────────"
warn "Se despliega lo que ya esté en $REMOTE/$BRANCH. Asegúrate de haber pusheado."
confirm "¿Continuar?"

log "Actualizando código en prod y lanzando el despliegue…"
# El `git pull` va antes de invocar el script: bash arranca prod-deploy.sh
# desde cero, ya con la versión actualizada (no se corrompe a mitad).
ssh -o BatchMode=yes -o ConnectTimeout=15 -t "$DEPLOY_SSH" \
  "cd '$REMOTE_DIR' && git pull '$REMOTE' '$BRANCH' && $REMOTE_ENV bash deploy/prod-deploy.sh $ACTION"

ok "Listo."
