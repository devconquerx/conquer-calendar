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

if docker info >/dev/null 2>&1; then
  echo "▶ Bajando el stack del worktree…"
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  echo "✅ Listo."
else
  echo "⚠️  Docker no está corriendo; no pude bajar el stack."
fi
