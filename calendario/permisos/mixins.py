from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RequierePermisoMixin(LoginRequiredMixin):
    permiso_requerido: str = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.permiso_requerido and not request.user.tiene_permiso(self.permiso_requerido):
            raise PermissionDenied(f"Falta permiso: {self.permiso_requerido}")
        return super().dispatch(request, *args, **kwargs)
