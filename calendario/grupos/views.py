import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View

from calendario.permisos.mixins import RequierePermisoMixin
from calendario.bookings.models import ConfigCorreoGrupo, ConfigCorreoMiembroGrupo

from .forms import ConfigCorreoGrupoForm, GrupoForm, GrupoMiembrosForm, GrupoPermisosForm, _usuarios_activos_context, _supervisores_disponibles_context
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
        from django.db.models import Count
        from calendario.event_types.models import EventTypeXHost
        from calendario.event_types.utils import event_types_visibles

        ctx = super().get_context_data(**kwargs)
        ctx['es_admin'] = self.request.user.es_admin

        # Nº de tipos de evento (de los que este usuario ve) en los que está
        # cada miembro, para la columna "Eventos" de la tabla.
        visibles_ids = event_types_visibles(self.request.user).values_list('id', flat=True)
        conteos = dict(
            EventTypeXHost.objects
            .filter(event_type_id__in=visibles_ids)
            .values_list('host_id')
            .annotate(total=Count('id'))
        )
        for grupo in ctx['grupos']:
            for membresia in grupo.membresias.all():
                membresia.usuario.num_eventos = conteos.get(membresia.usuario_id, 0)

        ctx['puede_editar_eventos'] = self.request.user.tiene_permiso('event_types.editar')
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

    def _miembros_grupo_context(self):
        return [
            {
                'id': m.usuario.pk,
                'nombre': m.usuario.get_full_name() or m.usuario.username,
                'email': m.usuario.email,
                'avatar': m.usuario.avatar_url or '',
                'iniciales': (
                    (m.usuario.first_name[:1] + m.usuario.last_name[:1]).upper()
                    or m.usuario.username[:2].upper()
                ),
            }
            for m in self.object.membresias.select_related('usuario').order_by(
                'usuario__first_name', 'usuario__last_name'
            )
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['grupo'] = self.object
        config, _ = ConfigCorreoGrupo.objects.get_or_create(grupo=self.object)
        ctx['correo_form'] = ConfigCorreoGrupoForm(instance=config)
        ctx['miembros_grupo'] = self._miembros_grupo_context()
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.POST.get('_form_type') == 'correos':
            return self._handle_correos(request)
        if request.POST.get('_form_type') == 'aplicar_correos':
            return self._handle_aplicar_correos(request)
        return super().post(request, *args, **kwargs)

    def _handle_correos(self, request):
        from django.shortcuts import redirect
        config, _ = ConfigCorreoGrupo.objects.get_or_create(grupo=self.object)
        form = ConfigCorreoGrupoForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, f'Correos del grupo "{self.object.nombre}" actualizados.')
            return redirect(request.path)
        permisos_form = self.get_form()
        return self.render_to_response(self.get_context_data(form=permisos_form, correo_form=form))

    def _handle_aplicar_correos(self, request):
        from django.shortcuts import redirect
        from calendario.bookings.models import PlantillaCorreo

        def _get_plantilla(field_name):
            pk = request.POST.get(field_name)
            if pk:
                try:
                    return PlantillaCorreo.objects.get(pk=pk)
                except PlantillaCorreo.DoesNotExist:
                    pass
            return None

        miembro_ids = []
        for v in request.POST.getlist('aplicar_miembros'):
            try:
                miembro_ids.append(int(v))
            except (ValueError, TypeError):
                pass

        if not miembro_ids:
            messages.error(request, 'Debes seleccionar al menos un miembro.')
            return redirect(request.path)

        plantilla_host = _get_plantilla('plantilla_confirmacion_host')
        plantilla_inv = _get_plantilla('plantilla_confirmacion_inv')
        plantilla_rec = _get_plantilla('plantilla_recordatorio')

        miembros_validos = list(
            self.object.membresias.filter(usuario_id__in=miembro_ids).values_list('usuario_id', flat=True)
        )

        for uid in miembros_validos:
            ConfigCorreoMiembroGrupo.objects.update_or_create(
                grupo=self.object,
                usuario_id=uid,
                defaults={
                    'plantilla_confirmacion_host': plantilla_host,
                    'plantilla_confirmacion_inv': plantilla_inv,
                    'plantilla_recordatorio': plantilla_rec,
                },
            )

        messages.success(
            request,
            f'Correos aplicados a {len(miembros_validos)} miembro(s) del grupo "{self.object.nombre}".',
        )
        return redirect(request.path)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Permisos del grupo "{self.object.nombre}" actualizados.')
        return response


class GrupoMiembrosUpdateView(LoginRequiredMixin, View):
    """Permite a un supervisor editar solo los miembros (no supervisores) de su grupo."""
    template_name = 'pages/panel/grupos/miembros_form.html'

    def _get_grupo_o_403(self, pk):
        grupo = get_object_or_404(Grupo, pk=pk)
        user = self.request.user
        if user.es_admin:
            return grupo
        if not GrupoXUsuario.objects.filter(grupo=grupo, usuario=user, es_supervisor=True).exists():
            raise PermissionDenied
        return grupo

    def get(self, request, pk):
        grupo = self._get_grupo_o_403(pk)
        form = GrupoMiembrosForm(grupo=grupo)
        return render(request, self.template_name, {
            'grupo': grupo,
            'miembros_disponibles': _usuarios_activos_context(),
            'initial_miembro_ids': json.dumps(form.initial_miembro_ids()),
        })

    def post(self, request, pk):
        grupo = self._get_grupo_o_403(pk)
        form = GrupoMiembrosForm(request.POST, grupo=grupo)
        form.save()
        messages.success(request, f'Miembros del grupo "{grupo.nombre}" actualizados.')
        return redirect(reverse_lazy('panel_grupos:grupo_list'))



class MiembroEventosView(LoginRequiredMixin, View):
    """Alta y baja masiva de un miembro del grupo en varios tipos de evento.

    GET  → JSON con los eventos visibles y si el miembro está en cada uno.
    POST → JSON; deja al miembro exactamente en los eventos marcados.

    Solo se tocan los tipos de evento dentro del alcance de quien edita: los que
    no ve no aparecen en la lista ni se ven afectados al guardar.
    """

    def _contexto_o_403(self, grupo_pk, usuario_pk):
        grupo = get_object_or_404(Grupo, pk=grupo_pk)
        user = self.request.user
        if not user.tiene_permiso('event_types.editar'):
            raise PermissionDenied('No tienes permisos para editar tipos de evento.')
        if not user.es_admin and not GrupoXUsuario.objects.filter(
            grupo=grupo, usuario=user, es_supervisor=True
        ).exists():
            raise PermissionDenied('No supervisas este grupo.')
        membresia = get_object_or_404(
            GrupoXUsuario.objects.select_related('usuario'), grupo=grupo, usuario_id=usuario_pk
        )
        return grupo, membresia.usuario

    def get(self, request, pk, usuario_pk):
        from calendario.event_types.models import EventTypeXHost
        from calendario.event_types.utils import event_types_visibles

        _, miembro = self._contexto_o_403(pk, usuario_pk)
        visibles = (
            event_types_visibles(request.user)
            .select_related('host')
            .distinct()
            .order_by('nombre')
        )
        asignados = set(
            EventTypeXHost.objects.filter(host=miembro).values_list('event_type_id', flat=True)
        )
        eventos = [
            {
                'id': et.pk,
                'nombre': et.nombre,
                'activo': et.activo,
                'duracion': et.duracion_minutos,
                'creador': et.host.nombre_display(),
                'asignado': et.pk in asignados,
                'es_creador': et.host_id == miembro.pk,
            }
            for et in visibles
        ]
        return JsonResponse({
            'miembro': miembro.nombre_display(),
            'eventos': eventos,
            'total_asignados': sum(1 for e in eventos if e['asignado']),
        })

    def post(self, request, pk, usuario_pk):
        from calendario.event_types.models import EventType, EventTypeXHost
        from calendario.event_types.utils import event_types_visibles

        _, miembro = self._contexto_o_403(pk, usuario_pk)
        visibles_ids = set(
            event_types_visibles(request.user).values_list('id', flat=True)
        )

        marcados = set()
        for raw in request.POST.getlist('eventos'):
            try:
                marcados.add(int(raw))
            except (TypeError, ValueError):
                continue
        marcados &= visibles_ids

        actuales = set(
            EventTypeXHost.objects
            .filter(host=miembro, event_type_id__in=visibles_ids)
            .values_list('event_type_id', flat=True)
        )

        # Al creador de un tipo de evento no se le saca de su propio pool: el
        # evento se quedaría sin organizador y dejaría de ofrecer horas.
        propios = set(
            EventType.objects.filter(pk__in=actuales, host=miembro).values_list('id', flat=True)
        )
        anadir = marcados - actuales
        quitar = (actuales - marcados) - propios

        with transaction.atomic():
            if quitar:
                EventTypeXHost.objects.filter(
                    host=miembro, event_type_id__in=quitar
                ).delete()
            if anadir:
                EventTypeXHost.objects.bulk_create([
                    EventTypeXHost(
                        event_type_id=et_id,
                        host=miembro,
                        prioridad=EventTypeXHost.PRIORIDAD_DEFECTO,
                    )
                    for et_id in anadir
                ])

        total = EventTypeXHost.objects.filter(
            host=miembro, event_type_id__in=visibles_ids
        ).count()
        return JsonResponse({
            'ok': True,
            'anadidos': len(anadir),
            'quitados': len(quitar),
            'total': total,
        })
