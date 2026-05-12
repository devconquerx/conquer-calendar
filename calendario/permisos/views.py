from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import RolForm
from .mixins import RequierePermisoMixin
from .models import Permiso, Rol


class RolListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'roles.ver'
    model = Rol
    template_name = 'pages/panel/roles/list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        return Rol.objects.prefetch_related('asignaciones', 'permisos').all()


class RolCreateView(RequierePermisoMixin, CreateView):
    permiso_requerido = 'roles.crear'
    model = Rol
    form_class = RolForm
    template_name = 'pages/panel/roles/form.html'
    success_url = reverse_lazy('panel_permisos:rol_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Rol '{self.object.nombre}' creado correctamente.")
        return response


class RolUpdateView(RequierePermisoMixin, UpdateView):
    permiso_requerido = 'roles.editar'
    model = Rol
    form_class = RolForm
    template_name = 'pages/panel/roles/form.html'
    success_url = reverse_lazy('panel_permisos:rol_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Rol '{self.object.nombre}' actualizado correctamente.")
        return response


class RolDeleteView(RequierePermisoMixin, DeleteView):
    permiso_requerido = 'roles.eliminar'
    model = Rol
    template_name = 'pages/panel/roles/confirm_delete.html'
    success_url = reverse_lazy('panel_permisos:rol_list')

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.nombre == 'admin':
            messages.error(request, "No se puede eliminar el rol 'admin'.")
            return redirect('panel_permisos:rol_list')
        messages.success(request, f"Rol '{obj.nombre}' eliminado.")
        return super().post(request, *args, **kwargs)


class PermisoListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'permisos.ver'
    model = Permiso
    template_name = 'pages/panel/permisos/list.html'
    context_object_name = 'permisos'

    def get_queryset(self):
        return Permiso.objects.prefetch_related('roles').all()
