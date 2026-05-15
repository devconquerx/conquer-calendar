from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from calendario.permisos.mixins import RequierePermisoMixin
from .forms import EventTypeForm, _hosts_queryset, _generar_slug_equipo
from .models import EventType, EventTypeXHost

User = get_user_model()


class EventTypeListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'event_types.ver'
    model = EventType
    template_name = 'pages/panel/event_types/list.html'
    context_object_name = 'event_types'
    paginate_by = 25

    def get_queryset(self):
        qs = EventType.objects.all() if self.request.user.es_admin \
            else EventType.objects.filter(host=self.request.user)

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
        ctx['filtros_count'] = len(ctx['filtro_organizadores']) + len(ctx['filtro_creadores'])
        if self.request.user.es_admin:
            ctx['organizadores_disponibles'] = list(
                User.objects.filter(is_active=True, roles_asignados__rol__nombre='host')
                .distinct().order_by('first_name', 'last_name', 'username')
            )
            ctx['creadores_disponibles'] = list(
                User.objects.filter(is_active=True, event_types__isnull=False)
                .distinct().order_by('first_name', 'last_name', 'username')
            )
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

    def get_queryset(self):
        if self.request.user.es_admin:
            return EventType.objects.all()
        return EventType.objects.filter(host=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hosts_disponibles'] = _hosts_disponibles_context()
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
        obj = self.get_object()
        messages.success(request, f"Tipo de evento '{obj.nombre}' eliminado.")
        return super().post(request, *args, **kwargs)


class EventTypeToggleActivoView(RequierePermisoMixin, View):
    permiso_requerido = 'event_types.editar'

    def post(self, request, pk):
        if request.user.es_admin:
            obj = get_object_or_404(EventType, pk=pk)
        else:
            obj = get_object_or_404(EventType, pk=pk, host=request.user)
        obj.activo = not obj.activo
        obj.save(update_fields=['activo', 'fecha_actualizacion'])
        estado = 'activado' if obj.activo else 'desactivado'
        messages.success(request, f"Tipo de evento '{obj.nombre}' {estado}.")
        return redirect('panel_event_types:event_type_list')
