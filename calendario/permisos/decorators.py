from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def requiere_permiso(codename):
    def deco(view_func):
        @wraps(view_func)
        @login_required
        def _wrap(request, *args, **kwargs):
            if not request.user.tiene_permiso(codename):
                raise PermissionDenied(f"Falta permiso: {codename}")
            return view_func(request, *args, **kwargs)
        return _wrap
    return deco
