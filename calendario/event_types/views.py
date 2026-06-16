from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from calendario.permisos.mixins import RequierePermisoMixin
from .forms import EventTypeForm, _hosts_queryset, _generar_slug_equipo
from .models import EventType, EventTypeXHost, EnlaceUnico

User = get_user_model()


class EventTypeListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'event_types.ver'
    model = EventType
    template_name = 'pages/panel/event_types/list.html'
    context_object_name = 'event_types'
    paginate_by = 25

    def get_queryset(self):
        if self.request.user.es_admin:
            qs = EventType.objects.all()
        else:
            from calendario.grupos.utils import miembros_de_mis_grupos
            q = Q(host=self.request.user) | Q(hosts_pool__host=self.request.user)
            grupo_ids = miembros_de_mis_grupos(self.request.user)
            if grupo_ids:
                q |= Q(host_id__in=grupo_ids)
            qs = EventType.objects.filter(q)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(nombre__icontains=q)

        organizadores = [v for v in self.request.GET.getlist('organizador') if v.isdigit()]
        if organizadores:
            qs = qs.filter(
                Q(hosts_pool__host_id__in=organizadores)
                | Q(host_id__in=organizadores, slug_equipo__isnull=True)
            )

        creadores = [v for v in self.request.GET.getlist('creador') if v.isdigit()]
        if creadores:
            qs = qs.filter(host_id__in=creadores)

        academia = self.request.GET.get('academia', '').strip()
        if academia:
            qs = qs.filter(host__email__iendswith=f'@{academia}')

        return (qs
                .annotate(num_hosts=Count('hosts_pool'))
                .select_related('host')
                .distinct()
                .order_by('nombre'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_q'] = self.request.GET.get('q', '')
        ctx['filtro_organizadores'] = self.request.GET.getlist('organizador')
        ctx['filtro_creadores'] = self.request.GET.getlist('creador')
        ctx['filtro_academia'] = self.request.GET.get('academia', '')
        ctx['filtros_count'] = (
            len(ctx['filtro_organizadores'])
            + len(ctx['filtro_creadores'])
            + (1 if ctx['filtro_academia'] else 0)
        )
        ctx['soy_organizador_ids'] = set(
            EventTypeXHost.objects.filter(host=self.request.user)
            .values_list('event_type_id', flat=True)
        )
        ctx['es_supervisor'] = (
            not self.request.user.es_admin
            and self.request.user.tiene_permiso('usuarios.editar_grupo')
        )
        if self.request.user.es_admin:
            ctx['organizadores_disponibles'] = list(
                User.objects.filter(is_active=True, roles_asignados__rol__nombre='host')
                .distinct().order_by('first_name', 'last_name', 'username')
            )
            ctx['creadores_disponibles'] = list(
                User.objects.filter(is_active=True, event_types__isnull=False)
                .distinct().order_by('first_name', 'last_name', 'username')
            )
        elif self.request.user.tiene_permiso('usuarios.editar_grupo'):
            from calendario.grupos.utils import miembros_de_mis_grupos
            miembros_ids = miembros_de_mis_grupos(self.request.user)
            miembros_ids_con_supervisor = miembros_ids + [self.request.user.pk]
            ctx['organizadores_disponibles'] = list(
                User.objects.filter(is_active=True, pk__in=miembros_ids_con_supervisor)
                .distinct().order_by('first_name', 'last_name', 'username')
            )
            ctx['creadores_disponibles'] = list(
                User.objects.filter(
                    is_active=True, pk__in=miembros_ids_con_supervisor,
                    event_types__isnull=False,
                ).distinct().order_by('first_name', 'last_name', 'username')
            )
        ctx['academias'] = sorted({
            u.email.split('@')[1]
            for u in ctx.get('creadores_disponibles', [])
            if u.email and '@' in u.email
        })
        return ctx


def _hosts_disponibles_context():
    return [
        {
            'id': u.pk,
            'nombre': (u.get_full_name() or u.username),
            'email': u.email,
            'avatar': u.avatar_url,
            'iniciales': (u.first_name[:1] + u.last_name[:1]).upper() or u.username[:2].upper(),
        }
        for u in _hosts_queryset()
    ]


class EventTypeCreateView(RequierePermisoMixin, CreateView):
    permiso_requerido = 'event_types.crear'
    model = EventType
    form_class = EventTypeForm
    template_name = 'pages/panel/event_types/form.html'
    success_url = reverse_lazy('panel_event_types:event_type_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hosts_disponibles'] = _hosts_disponibles_context()
        return ctx

    def dispatch(self, request, *args, **kwargs):
        from calendario.grupos.utils import usuario_bloqueado
        if usuario_bloqueado(request.user, 'bloquear_crear_event_types', request):
            messages.error(request, 'Tu grupo no te autoriza para crear eventos.')
            return redirect('panel_event_types:event_type_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.host = self.request.user
        if form.cleaned_data.get('es_equipo'):
            obj.slug_equipo = _generar_slug_equipo(obj.nombre)
        else:
            obj.slug_equipo = None
        try:
            obj.full_clean(exclude=['slug'])
        except ValidationError as e:
            for field, errs in e.message_dict.items():
                for err in errs:
                    field_name = field if (field != '__all__' and field in form.fields) else None
                    form.add_error(field_name, err)
            return self.form_invalid(form)
        hosts_seleccionados = (
            list(form.cleaned_data.get('hosts') or [])
            if form.cleaned_data.get('es_equipo') else []
        )
        with transaction.atomic():
            obj.save()
            EventTypeXHost.objects.bulk_create([
                EventTypeXHost(event_type=obj, host=h) for h in hosts_seleccionados
            ])
        self.object = obj
        messages.success(self.request, f"Tipo de evento '{obj.nombre}' creado.")
        return redirect(self.get_success_url())


class EventTypeUpdateView(RequierePermisoMixin, UpdateView):
    permiso_requerido = 'event_types.editar'
    model = EventType
    form_class = EventTypeForm
    template_name = 'pages/panel/event_types/form.html'
    success_url = reverse_lazy('panel_event_types:event_type_list')

    def _es_supervisor_del_evento(self, obj):
        from calendario.grupos.utils import miembros_de_mis_grupos
        return obj.host_id in miembros_de_mis_grupos(self.request.user)

    def _es_solo_lectura(self):
        obj = self.get_object()
        if self.request.user.es_admin:
            return False
        if self._es_supervisor_del_evento(obj):
            return False
        if obj.host == self.request.user:
            from calendario.grupos.utils import usuario_bloqueado
            if usuario_bloqueado(self.request.user, 'bloquear_editar_event_types', self.request):
                return True
            return False
        return True

    def get_queryset(self):
        if self.request.user.es_admin:
            return EventType.objects.all()
        from calendario.grupos.utils import miembros_de_mis_grupos
        q = Q(host=self.request.user) | Q(hosts_pool__host=self.request.user)
        grupo_ids = miembros_de_mis_grupos(self.request.user)
        if grupo_ids:
            q |= Q(host_id__in=grupo_ids)
        return EventType.objects.filter(q).distinct()

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and self._es_solo_lectura():
            messages.error(request, 'Tu grupo no te autoriza para editar este evento.')
            return redirect('panel_event_types:event_type_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hosts_disponibles'] = _hosts_disponibles_context()
        ctx['readonly'] = self._es_solo_lectura()
        return ctx

    def form_valid(self, form):
        obj = form.save(commit=False)
        if form.cleaned_data.get('es_equipo'):
            if not obj.slug_equipo:
                obj.slug_equipo = _generar_slug_equipo(obj.nombre, exclude_pk=obj.pk)
        else:
            obj.slug_equipo = None
        try:
            obj.full_clean(exclude=['slug'])
        except ValidationError as e:
            for field, errs in e.message_dict.items():
                for err in errs:
                    field_name = field if (field != '__all__' and field in form.fields) else None
                    form.add_error(field_name, err)
            return self.form_invalid(form)
        hosts_seleccionados = (
            list(form.cleaned_data.get('hosts') or [])
            if form.cleaned_data.get('es_equipo') else []
        )
        with transaction.atomic():
            obj.save()
            EventTypeXHost.objects.filter(event_type=obj).delete()
            EventTypeXHost.objects.bulk_create([
                EventTypeXHost(event_type=obj, host=h) for h in hosts_seleccionados
            ])
        self.object = obj
        messages.success(self.request, f"Tipo de evento '{obj.nombre}' actualizado.")
        return redirect(self.get_success_url())


class EventTypeDeleteView(RequierePermisoMixin, DeleteView):
    permiso_requerido = 'event_types.eliminar'
    model = EventType
    template_name = 'pages/panel/event_types/confirm_delete.html'
    success_url = reverse_lazy('panel_event_types:event_type_list')

    def get_queryset(self):
        if self.request.user.es_admin:
            return EventType.objects.all()
        return EventType.objects.filter(host=self.request.user)

    def post(self, request, *args, **kwargs):
        if not request.user.es_admin:
            from calendario.grupos.utils import usuario_bloqueado
            if usuario_bloqueado(request.user, 'bloquear_eliminar_event_types', request):
                messages.error(request, 'Tu grupo no te autoriza para eliminar eventos.')
                return redirect('panel_event_types:event_type_list')
        obj = self.get_object()
        messages.success(request, f"Tipo de evento '{obj.nombre}' eliminado.")
        return super().post(request, *args, **kwargs)


@login_required
@require_POST
def generar_enlace_unico(request, pk):
    if request.user.es_admin:
        event_type = get_object_or_404(EventType, pk=pk)
    else:
        from django.db.models import Q
        from calendario.grupos.utils import miembros_de_mis_grupos
        grupo_ids = miembros_de_mis_grupos(request.user)
        q = Q(host=request.user) | Q(hosts_pool__host=request.user)
        if grupo_ids:
            q |= Q(host_id__in=grupo_ids)
        event_type = get_object_or_404(EventType.objects.filter(q).distinct(), pk=pk)

    enlace = EnlaceUnico.objects.create(event_type=event_type, creado_por=request.user)
    url = request.build_absolute_uri(f'/u/{enlace.token}/')
    return JsonResponse({'url': url})


class EventTypeToggleActivoView(RequierePermisoMixin, View):
    permiso_requerido = 'event_types.editar'

    def post(self, request, pk):
        if not request.user.es_admin:
            from calendario.grupos.utils import usuario_bloqueado
            if usuario_bloqueado(request.user, 'bloquear_activar_event_types', request):
                messages.error(request, 'Tu grupo no te autoriza para activar o desactivar eventos.')
                return redirect('panel_event_types:event_type_list')
        if request.user.es_admin:
            obj = get_object_or_404(EventType, pk=pk)
        else:
            from calendario.grupos.utils import miembros_de_mis_grupos
            grupo_ids = miembros_de_mis_grupos(request.user)
            obj = get_object_or_404(
                EventType,
                Q(pk=pk) & (Q(host=request.user) | Q(host_id__in=grupo_ids))
            )
        obj.activo = not obj.activo
        obj.save(update_fields=['activo', 'fecha_actualizacion'])
        estado = 'activado' if obj.activo else 'desactivado'
        messages.success(request, f"Tipo de evento '{obj.nombre}' {estado}.")
        return redirect('panel_event_types:event_type_list')
