import logging

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
from .models import EventType, EventTypeXHost, EnlaceUnico, DisponibilidadEtxh, DisponibilidadFechaEtxh

User = get_user_model()
logger = logging.getLogger(__name__)


class EventTypeListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'event_types.ver'
    model = EventType
    template_name = 'pages/panel/event_types/list.html'
    context_object_name = 'event_types'
    paginate_by = 24

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


def _invalidar_slots_sin_romper(event_type_id):
    """Invalida los slots cacheados sin dejar que un fallo de caché tumbe el guardado.

    Se llama en `on_commit`, con el evento ya escrito: una excepción aquí sería un
    500 sobre algo que en realidad salió bien. Los slots cacheados caducan por TTL
    en segundos, así que perder una invalidación no deja nada inconsistente.
    """
    from calendario.bookings.services import invalidar_slots
    try:
        invalidar_slots(event_type_id)
    except Exception:
        logger.warning(
            'No se pudo invalidar la caché de slots del event_type %s',
            event_type_id, exc_info=True,
        )


def _puede_configurar_prioridad(user, event_type):
    """
    Quién puede repartir la prioridad del round-robin de un evento:

      - el administrador general, en cualquier evento;
      - quien creó el evento;
      - el supervisor del grupo al que pertenece el creador.

    Un organizador que solo está en el pool queda fuera: ve el evento, pero no
    decide el reparto. `event_type=None` es el alta, donde el creador es por
    definición quien lo está creando.
    """
    if getattr(user, 'es_admin', False):
        return True
    if event_type is None or event_type.host_id == user.pk:
        return True
    from calendario.grupos.utils import miembros_de_mis_grupos
    return event_type.host_id in miembros_de_mis_grupos(user)


def _prioridades_del_post(post, host_ids):
    """
    Lee las prioridades que envía el modal de organizadores ('prioridad_<host_id>').

    Todo lo que falte, no sea un entero o se salga del rango 0..3 cae a la prioridad
    por defecto: el modal es la única vía normal de tocar esto, pero un POST a mano
    no debe poder meter valores raros en la BD. El 0 sí es un valor legítimo (deja
    al organizador fuera del reparto), así que pasa el filtro como cualquier otro.
    """
    minimo = EventTypeXHost.PRIORIDAD_MIN
    maximo = EventTypeXHost.PRIORIDAD_MAX
    defecto = EventTypeXHost.PRIORIDAD_DEFECTO
    prioridades = {}
    for hid in host_ids:
        try:
            valor = int(post.get(f'prioridad_{hid}', defecto))
        except (TypeError, ValueError):
            valor = defecto
        prioridades[hid] = valor if minimo <= valor <= maximo else defecto
    return prioridades


class EventTypeCreateView(RequierePermisoMixin, CreateView):
    permiso_requerido = 'event_types.crear'
    model = EventType
    form_class = EventTypeForm
    template_name = 'pages/panel/event_types/form.html'
    success_url = reverse_lazy('panel_event_types:event_type_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hosts_disponibles'] = _hosts_disponibles_context()
        ctx['prioridades_iniciales'] = {}
        ctx['puede_prioridad'] = _puede_configurar_prioridad(self.request.user, None)
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
        prioridades = _prioridades_del_post(
            self.request.POST, [h.pk for h in hosts_seleccionados],
        )
        with transaction.atomic():
            obj.save()
            EventTypeXHost.objects.bulk_create([
                EventTypeXHost(event_type=obj, host=h, prioridad=prioridades[h.pk])
                for h in hosts_seleccionados
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
        ctx['prioridades_iniciales'] = dict(
            EventTypeXHost.objects
            .filter(event_type=self.object)
            .values_list('host_id', 'prioridad')
        )
        ctx['puede_prioridad'] = _puede_configurar_prioridad(self.request.user, self.object)
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
        nuevos_ids = {h.pk for h in hosts_seleccionados}
        # Ocultar el botón no basta: sin permiso se ignoran las prioridades que
        # venga trayendo el POST y las filas existentes se quedan como estaban.
        puede_prioridad = _puede_configurar_prioridad(self.request.user, obj)
        prioridades = (
            _prioridades_del_post(self.request.POST, nuevos_ids)
            if puede_prioridad else {}
        )
        defecto = EventTypeXHost.PRIORIDAD_DEFECTO
        with transaction.atomic():
            obj.save()
            existing_ids = set(
                EventTypeXHost.objects.filter(event_type=obj).values_list('host_id', flat=True)
            )
            EventTypeXHost.objects.filter(event_type=obj, host_id__in=existing_ids - nuevos_ids).delete()
            EventTypeXHost.objects.bulk_create([
                EventTypeXHost(event_type=obj, host_id=hid,
                               prioridad=prioridades.get(hid, defecto))
                for hid in nuevos_ids - existing_ids
            ])
            # Los que ya estaban en el pool conservan su fila (y con ella el orden
            # de entrada, que sigue siendo el último desempate): solo se reescribe
            # la prioridad, y únicamente si cambió.
            if puede_prioridad:
                cambiadas = []
                for pivot in EventTypeXHost.objects.filter(
                    event_type=obj, host_id__in=nuevos_ids & existing_ids,
                ):
                    if pivot.prioridad != prioridades[pivot.host_id]:
                        pivot.prioridad = prioridades[pivot.host_id]
                        cambiadas.append(pivot)
                if cambiadas:
                    EventTypeXHost.objects.bulk_update(cambiadas, ['prioridad'])
            # El pool y el rango de fechas deciden qué horas se ofrecen, así que
            # tocarlos invalida los slots cacheados en vez de esperar a que caduquen
            # solos. Corre después del commit y es solo una optimización: si la
            # caché falla, el evento ya está guardado y no se le puede devolver un
            # error al usuario, así que se traga y se deja caducar por TTL.
            transaction.on_commit(lambda: _invalidar_slots_sin_romper(obj.pk))
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


import json as _json

@login_required
def disponibilidad_etxh_view(request, pk, host_pk):
    if not request.user.es_admin:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    et = get_object_or_404(EventType, pk=pk)
    if request.method == 'GET':
        etxh = EventTypeXHost.objects.filter(event_type=et, host_id=host_pk).first()
        franjas, fechas = [], []
        if etxh:
            franjas = [
                {
                    'dia_semana': d.dia_semana,
                    'hora_inicio': d.hora_inicio.strftime('%H:%M'),
                    'hora_fin': d.hora_fin.strftime('%H:%M'),
                }
                for d in etxh.disponibilidad.all()
            ]
            fechas = [
                {
                    'fecha': f.fecha.isoformat(),
                    'hora_inicio': f.hora_inicio.strftime('%H:%M') if f.hora_inicio else None,
                    'hora_fin': f.hora_fin.strftime('%H:%M') if f.hora_fin else None,
                }
                for f in etxh.disponibilidad_fechas.all()
            ]
        return JsonResponse({'franjas': franjas, 'fechas': fechas})

    if request.method == 'POST':
        etxh = get_object_or_404(EventTypeXHost, event_type=et, host_id=host_pk)
        try:
            data = _json.loads(request.body)
            franjas_raw = data.get('franjas', [])
            fechas_raw = data.get('fechas', [])
        except (_json.JSONDecodeError, AttributeError):
            return JsonResponse({'error': 'JSON inválido'}, status=400)

        nuevas_franjas = []
        for f in franjas_raw:
            try:
                dia = int(f['dia_semana'])
                assert 0 <= dia <= 6
            except (KeyError, ValueError, AssertionError):
                return JsonResponse({'error': 'Día inválido'}, status=400)
            nuevas_franjas.append(DisponibilidadEtxh(
                etxh=etxh, dia_semana=dia,
                hora_inicio=f['hora_inicio'], hora_fin=f['hora_fin'],
            ))

        nuevas_fechas = []
        for f in fechas_raw:
            nuevas_fechas.append(DisponibilidadFechaEtxh(
                etxh=etxh,
                fecha=f['fecha'],
                hora_inicio=f.get('hora_inicio') or None,
                hora_fin=f.get('hora_fin') or None,
            ))

        with transaction.atomic():
            etxh.disponibilidad.all().delete()
            etxh.disponibilidad_fechas.all().delete()
            DisponibilidadEtxh.objects.bulk_create(nuevas_franjas)
            DisponibilidadFechaEtxh.objects.bulk_create(nuevas_fechas)
        return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


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
