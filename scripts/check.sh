#!/usr/bin/env bash
# Comprobación completa antes de desplegar.
#
#   ./scripts/check.sh            → todo
#   ./scripts/check.sh --rapido   → salta los e2e (no compila ni abre navegador)
#
# Cada capa caza una clase distinta de fallo:
#   1. unit + componente : lógica y render de cada pantalla (jsdom, ~2 s)
#   2. render SSR        : que ninguna etapa de ninguna marca reviente
#   3. backend           : que el dato llegue y se guarde donde toca
#   4. build             : que compile cliente y SSR
#   5. e2e               : el recorrido real en navegador, con el bundle compilado
#
# Devuelve 0 solo si TODAS pasan.
set -uo pipefail
cd "$(dirname "$0")/.."

RAPIDO=0
[[ "${1:-}" == "--rapido" ]] && RAPIDO=1

verde() { printf '\033[32m%s\033[0m\n' "$1"; }
rojo()  { printf '\033[31m%s\033[0m\n' "$1"; }
titulo(){ printf '\n\033[1m── %s\033[0m\n' "$1"; }

FALLOS=()
paso() {
  local nombre="$1"; shift
  titulo "$nombre"
  if "$@"; then verde "✓ $nombre"; else rojo "✗ $nombre"; FALLOS+=("$nombre"); fi
}

paso "Frontend · unitarios, componente y render SSR" bash -c 'cd frontend && npm test'

if docker compose ps django 2>/dev/null | grep -q Up; then
  paso "Backend · Django" bash -c \
    'docker compose exec -T django bash -c "while IFS= read -r -d \"\" l; do export \"\$l\"; done < /proc/1/environ; python manage.py test tests -v1 --noinput"'
else
  rojo "⚠ Backend saltado: el contenedor django no está arriba (docker compose up -d)"
  FALLOS+=("Backend (no ejecutado)")
fi

if [[ $RAPIDO -eq 0 ]]; then
  paso "Frontend · build cliente y SSR" bash -c 'cd frontend && npm run build && npm run build:ssr'
  paso "E2E · recorrido en navegador (escritorio y móvil)" bash -c 'cd frontend && npx playwright test'
else
  printf '\n(--rapido: build y e2e saltados)\n'
fi

echo
if [[ ${#FALLOS[@]} -eq 0 ]]; then
  verde "TODO EN VERDE — listo para desplegar"
  exit 0
fi
rojo "FALLÓ: ${FALLOS[*]}"
rojo "NO despliegues hasta que esté en verde."
exit 1
