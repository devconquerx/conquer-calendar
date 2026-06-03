from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from calendario.permisos.mixins import RequierePermisoMixin
from .forms import GrupoForm, GrupoPermisosForm, _usuarios_activos_context, _supervisores_disponibles_context
from .models import Grupo, GrupoXUsuario


class GrupoListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'grupos.ver'
    model = Grupo
    template_name = 'pages/panel/grupos/list.html'
    context_object_name = 'grupos'

    def get_queryset(self):
        qs = Grupo.objects.prefetch_related(
            'membresias__usuario__roles_asignados__rol'
        )
        if not self.request.user.es_admin:
            qs = qs.filter(
                membresias__usuario=self.request.user,
                membresias__es_supervisor=True,
            )
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['es_admin'] = self.request.user.es_admin
        return ctx


class GrupoCreateView(RequierePermisoMixin, CreateView):
    permiso_requerido = 'grupos.crear'
    model = Grupo
    form_class = GrupoForm
    template_name = 'pages/panel/grupos/form.html'
    success_url = reverse_lazy('panel_grupos:grupo_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo grupo'
        ctx['supervisores_disponibles'] = _supervisores_disponibles_context()
        ctx['miembros_disponibles'] = _usuarios_activos_context()
        ctx['initial_supervisor_ids'] = '[]'
        ctx['initial_miembro_ids'] = '[]'
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Grupo "{self.object.nombre}" creado correctamente.')
        return response

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class GrupoUpdateView(RequierePermisoMixin, UpdateView):
    permiso_requerido = 'grupos.editar'
    model = Grupo
    form_class = GrupoForm
    template_name = 'pages/panel/grupos/form.html'
    success_url = reverse_lazy('panel_grupos:grupo_list')

    def get_context_data(self, **kwargs):
        import json
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar grupo: {self.object.nombre}'
        ctx['supervisores_disponibles'] = _supervisores_disponibles_context()
        ctx['miembros_disponibles'] = _usuarios_activos_context()
        form = ctx['form']
        ctx['initial_supervisor_ids'] = json.dumps(form.initial_supervisor_ids())
        ctx['initial_miembro_ids'] = json.dumps(form.initial_miembro_ids())
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Grupo "{self.object.nombre}" actualizado correctamente.')
        return response

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class GrupoDeleteView(RequierePermisoMixin, DeleteView):
    permiso_requerido = 'grupos.eliminar'
    model = Grupo
    template_name = 'pages/panel/grupos/confirm_delete.html'
    success_url = reverse_lazy('panel_grupos:grupo_list')

    def post(self, request, *args, **kwargs):
        nombre = self.get_object().nombre
        response = super().post(request, *args, **kwargs)
        messages.success(request, f'Grupo "{nombre}" eliminado.')
        return response


class GrupoPermisosView(LoginRequiredMixin, UpdateView):
    """Vista para que supervisores (y admins) editen los flags de permisos del grupo."""
    model = Grupo
    form_class = GrupoPermisosForm
    template_name = 'pages/panel/grupos/permisos_form.html'
    success_url = reverse_lazy('panel_grupos:grupo_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        autorizado = False
        if request.user.tiene_permiso('grupos.editar'):
            autorizado = True
        elif request.user.tiene_permiso('grupos.editar_propio'):
            autorizado = GrupoXUsuario.objects.filter(
                grupo_id=kwargs.get('pk'),
                usuario=request.user,
                es_supervisor=True,
            ).exists()
        if not autorizado:
            raise PermissionDenied('No tienes permisos para editar este grupo.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['grupo'] = self.object
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Permisos del grupo "{self.object.nombre}" actualizados.')
        return response
