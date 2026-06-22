#!/usr/bin/env bash
#
# Hook de Superset al CREAR un worktree de conquer-calendar (CWD = worktree).
# Superset inyecta $SUPERSET_ROOT_PATH = ruta del repo principal.
#
# Modelo: DB compartida (postgres del principal) + Redis/Celery propios del worktree.
#   1. Copia los env files ignorados (.envs/) desde el principal.
#   2. Genera un .env con COMPOSE_PROJECT_NAME + APP_HOST únicos y COMPOSE_FILE
#      apuntando a local.yml + los overlays superset.* del repo principal (ruta absoluta).
#   3. Asegura el postgres del principal arriba y en la red compartida.
#   Levantas con el preset "🐳 Up" (docker compose up -d).
#
# Re-ejecutable (idempotente).
set -u

WT="$(pwd -P)"
ROOT="${SUPERSET_ROOT_PATH:-$WT}"
ROOT="$(cd "$ROOT" 2>/dev/null && pwd -P || echo "$WT")"

if [ "$WT" = "$ROOT" ]; then
  echo "ℹ️  Estoy en el repo principal ($WT); no preparo worktree."
  exit 0
fi

echo "▶ Preparando worktree: $WT"
echo "  Repo principal:      $ROOT"

# 1) Copiar env files ignorados desde el principal
if [ -d "$ROOT/.envs" ]; then
  cp -R "$ROOT/.envs" "$WT/" || { echo "❌ No pude copiar .envs"; exit 1; }
  echo "✅ .envs copiado desde el principal"
else
  echo "⚠️  No existe $ROOT/.envs"
fi
mkdir -p "$WT/calendario_logs" "$WT/calendario-media"

# 2) Generar .env único (slug desde la rama git; fallback al nombre de carpeta)
BRANCH="$(git -C "$WT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
RAW="${BRANCH:-$(basename "$WT")}"
slug="$(printf '%s' "$RAW" | tr '[:upper:]' '[:lower:]' | sed 's#[^a-z0-9-]#-#g; s#-\{2,\}#-#g; s#^-##; s#-$##')"
[ -z "$slug" ] && slug="$(basename "$WT" | tr '[:upper:]' '[:lower:]' | sed 's#[^a-z0-9-]#-#g')"
PROJECT="conquercalendar-${slug}"
APP_HOST="${slug}.localhost"
# Puerto de Vite propio por worktree (determinista, rango 5200-5299) para no chocar en 5173.
VITE_PORT=$((5200 + $(printf '%s' "$slug" | cksum | cut -d' ' -f1) % 100))

cat > "$WT/.env" <<EOF
# Autogenerado por .superset/worktree-setup.sh — no commitear.
# local.yml es del worktree (build context); los overlays superset.* se leen del repo principal.
COMPOSE_PROJECT_NAME=${PROJECT}
APP_HOST=${APP_HOST}
COMPOSE_FILE=local.yml:${ROOT}/superset.yml:${ROOT}/superset.shared.yml
VITE_PORT=${VITE_PORT}
EOF
echo "✅ .env generado -> proyecto=${PROJECT}  host=${APP_HOST}  vite=${VITE_PORT}  (DB compartida)"

# Overrides locales para aislar Vite por worktree (settings + vite config). Copiados del principal.
cp "$ROOT/config/settings/superset_worktree.py" "$WT/config/settings/superset_worktree.py" 2>/dev/null \
  && echo "✅ settings override copiado" || echo "⚠️  no pude copiar el settings override"
cp "$ROOT/frontend/vite.config.superset.mjs" "$WT/frontend/vite.config.superset.mjs" 2>/dev/null \
  && echo "✅ vite config override copiado" || echo "⚠️  no pude copiar el vite override"

# Credenciales de Postgres (desde los env recién copiados)
PGFILE="$WT/.envs/.local/.postgres"
PGUSER="$(grep -E '^POSTGRES_USER=' "$PGFILE" 2>/dev/null | head -1 | cut -d= -f2-)"
PGDB="$(grep   -E '^POSTGRES_DB='   "$PGFILE" 2>/dev/null | head -1 | cut -d= -f2-)"

# 3) Asegurar red compartida + postgres del principal arriba (best-effort)
if docker info >/dev/null 2>&1; then
  docker network create conquercalendar-db >/dev/null 2>&1 || true
  MAIN_PROJECT="$(grep -E '^COMPOSE_PROJECT_NAME=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
  [ -z "${MAIN_PROJECT:-}" ] && MAIN_PROJECT="$(basename "$ROOT" | tr '[:upper:]' '[:lower:]' | sed 's#[^a-z0-9_-]#-#g')"
  echo "▶ Asegurando postgres del principal ($MAIN_PROJECT) en la red compartida…"
  docker compose -p "$MAIN_PROJECT" -f "$ROOT/local.yml" -f "$ROOT/superset.yml" up -d postgres >/dev/null 2>&1 || \
    echo "⚠️  No pude levantar el postgres del principal; asegúrate de tenerlo arriba antes de usar el worktree."
  # Asegurar (idempotente) que el postgres del principal esté en la red compartida,
  # aunque se haya levantado sin superset.yml (con local.yml pelado).
  docker network connect conquercalendar-db "${MAIN_PROJECT}-postgres-1" --alias postgres >/dev/null 2>&1 || true
else
  echo "⚠️  Docker no está corriendo; solo dejé los archivos listos."
fi

cat <<EOF

════════════════════════════════════════════════════════════
 Worktree listo: ${PROJECT}   (comparte la DB del principal)
   Levantar:  preset 🐳 Up  (levanta contenedores + Vite en el puerto ${VITE_PORT})
   Abrir:     http://${APP_HOST}
   Servicios: django + redis + celeryworker + celerybeat (postgres compartido)
   Vite:      puerto propio ${VITE_PORT} (django_vite ya apunta ahí; sin choques en 5173)
   Nota:      NO corre migrate (no muta la DB compartida).
════════════════════════════════════════════════════════════
EOF
