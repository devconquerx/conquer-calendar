#!/usr/bin/env bash
#
# Hook de Superset al ELIMINAR un worktree (CWD = worktree).
# Baja django/redis/celery del worktree. NUNCA -v (la DB es compartida con el principal).
set -u

WT="$(pwd -P)"
ROOT="${SUPERSET_ROOT_PATH:-$WT}"
ROOT="$(cd "$ROOT" 2>/dev/null && pwd -P || echo "$WT")"

if [ "$WT" = "$ROOT" ]; then
  echo "ℹ️  Repo principal; no hago teardown."
  exit 0
fi

# Borramos por etiqueta del proyecto (robusto: NO depende del compose file, que
# desaparece al borrarse el worktree). NUNCA volúmenes (la DB es compartida).
PROJECT="$(grep -E '^COMPOSE_PROJECT_NAME=' "$WT/.env" 2>/dev/null | head -1 | cut -d= -f2)"
if [ -n "$PROJECT" ] && docker info >/dev/null 2>&1; then
  echo "▶ Bajando el stack del worktree ($PROJECT)…"
  cids=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")
  [ -n "$cids" ] && printf '%s\n' "$cids" | xargs docker rm -f >/dev/null 2>&1
  nids=$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT")
  [ -n "$nids" ] && printf '%s\n' "$nids" | xargs docker network rm >/dev/null 2>&1
  echo "✅ Listo."
else
  echo "⚠️  Docker no corre o no hallé COMPOSE_PROJECT_NAME; nada que bajar."
fi
