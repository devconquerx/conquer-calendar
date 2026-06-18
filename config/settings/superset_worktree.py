"""Settings para worktrees de Superset: igual que local, pero el dev server de Vite
usa un puerto propio por worktree (evita colisiones en 5173 entre worktrees).

Lo copia .superset/worktree-setup.sh dentro de cada worktree (archivo local, no del equipo).
El worktree arranca con DJANGO_SETTINGS_MODULE=config.settings.superset_worktree y
DJANGO_VITE_DEV_SERVER_PORT=<puerto único> (inyectado por superset.shared.yml).
"""
from .local import *  # noqa
import os as _os

_port = _os.environ.get("DJANGO_VITE_DEV_SERVER_PORT")
if _port:
    DJANGO_VITE["default"]["dev_server_port"] = int(_port)  # noqa: F405
