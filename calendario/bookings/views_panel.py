from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView

from calendario.permisos.mixins import RequierePermisoMixin
from calendario.users.models import User
from .models import CancelacionReserva, Reserva
from .services import cancelar_reserva, eliminar_reserva


def _miembros_grupo(user):
    """PKs de todos los miembros en grupos donde user es supervisor."""
    from calendario.grupos.utils import miembros_de_mis_grupos
    return miembros_de_mis_grupos(user)

import logging
logger = logging.getLogger(__name__)


_DIAS_ES  = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
_MESES_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _fmt_rango(inicio_utc, fin_utc, tz):
    """Devuelve dict con hora_inicio, hora_fin y fecha en español."""
    inicio = inicio_utc.astimezone(tz)
    fin    = fin_utc.astimezone(tz)
    return {
        'hora_inicio': f"{inicio.hour}:{inicio.minute:02d}",
        'hora_fin':    f"{fin.hour}:{fin.minute:02d}",
        'fecha': (
            f"{_DIAS_ES[inicio.weekday()]}, "
            f"{inicio.day} de {_MESES_ES[inicio.month - 1]} "
            f"de {inicio.year}"
        ),
    }


class ReservaListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'reservas.ver_propias'
    model = Reserva
    template_name = 'pages/panel/reservas/list.html'
    context_object_name = 'reservas'
    paginate_by = 25

    def get_queryset(self):
        qs = (Reserva.objects
              .filter(
                  Q(event_type__host=self.request.user) |
                  Q(host=self.request.user)
              )
              .select_related('event_type', 'host')
              .distinct())

        email   = self.request.GET.get('email', '').strip()
        estado  = self.request.GET.get('estado', '').strip()
        orden   = self.request.GET.get('orden', 'reciente')
        periodo = self.request.GET.get('periodo', '').strip()

        if email:
            qs = qs.filter(email_invitado__icontains=email)
        if estado in ('confirmada', 'cancelada'):
            qs = qs.filter(estado=estado)
        if periodo == 'proximas':
            qs = qs.filter(inicio_utc__gt=timezone.now())
        elif periodo == 'pasadas':
            qs = qs.filter(inicio_utc__lte=timezone.now())

        if orden == 'antiguo':
            qs = qs.order_by('fecha_creacion')
        else:
            qs = qs.order_by('-fecha_creacion')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_email']   = self.request.GET.get('email', '')
        ctx['filtro_estado']  = self.request.GET.get('estado', '')
        ctx['filtro_orden']   = self.request.GET.get('orden', 'reciente')
        ctx['filtro_periodo'] = self.request.GET.get('periodo', '')
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx


class ReservaDetailView(RequierePermisoMixin, DetailView):
    permiso_requerido = 'reservas.ver_propias'
    model = Reserva
    template_name = 'pages/panel/reservas/detail.html'
    context_object_name = 'reserva'

    def get_queryset(self):
        qs = Reserva.objects.select_related('event_type', 'host')
        if self.request.user.tiene_permiso('reservas.ver_todas'):
            return qs
        miembro_ids = _miembros_grupo(self.request.user)
        return qs.filter(
            Q(event_type__host=self.request.user) |
            Q(host=self.request.user) |
            Q(event_type__host_id__in=miembro_ids) |
            Q(host_id__in=miembro_ids)
        ).distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        reserva = self.object
        fin_utc = reserva.fin_utc

        # TZ del host
        try:
            tz_host = ZoneInfo(reserva.host.timezone)
        except (ZoneInfoNotFoundError, Exception):
            tz_host = ZoneInfo('UTC')

        # TZ del invitado (fallback a la del host si no se guardó)
        tz_inv_str = reserva.timezone_invitado or reserva.host.timezone
        try:
            tz_inv = ZoneInfo(tz_inv_str)
        except (ZoneInfoNotFoundError, Exception):
            tz_inv = tz_host
            tz_inv_str = reserva.host.timezone

        ctx['rango_invitado'] = _fmt_rango(reserva.inicio_utc, fin_utc, tz_inv)
        ctx['rango_invitado']['tz'] = tz_inv_str
        ctx['rango_host']     = _fmt_rango(reserva.inicio_utc, fin_utc, tz_host)
        ctx['rango_host']['tz'] = reserva.host.timezone
        ctx['misma_tz'] = (tz_inv_str == reserva.host.timezone)

        # UTC de Google Calendar para comparar con el de la BD
        ctx['gcal_utc'] = None
        ctx['gcal_coincide'] = None
        if reserva.google_event_id and reserva.google_sync_estado == Reserva.GoogleSyncEstado.SINCRONIZADO:
            try:
                from calendario.google_calendar.services import obtener_servicio_calendar
                from datetime import datetime, timezone as dt_timezone
                svc = obtener_servicio_calendar(reserva.host.email)
                ev  = svc.events().get(calendarId='primary', eventId=reserva.google_event_id).execute()
                gcal_start = datetime.fromisoformat(ev['start']['dateTime']).astimezone(dt_timezone.utc)
                gcal_end   = datetime.fromisoformat(ev['end']['dateTime']).astimezone(dt_timezone.utc)
                ctx['gcal_utc'] = {
                    'inicio': f"{gcal_start.hour:02d}:{gcal_start.minute:02d}",
                    'fin':    f"{gcal_end.hour:02d}:{gcal_end.minute:02d}",
                    'fecha':  gcal_start.strftime('%d/%m/%Y'),
                }
                ctx['gcal_coincide'] = (
                    gcal_start == reserva.inicio_utc.astimezone(dt_timezone.utc) and
                    gcal_end   == reserva.fin_utc.astimezone(dt_timezone.utc)
                )
            except Exception:
                logger.exception('ReservaDetailView: error consultando GCal event_id=%s', reserva.google_event_id)

        return ctx


class ReservaAdminListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'reservas.ver_todas'
    model = Reserva
    template_name = 'pages/panel/reservas/admin_list.html'
    context_object_name = 'reservas'
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.tiene_permiso('reservas.ver_todas') or request.user.tiene_permiso('grupos.ver'):
            return super(RequierePermisoMixin, self).dispatch(request, *args, **kwargs)
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    def _es_supervisor(self):
        return (not self.request.user.tiene_permiso('reservas.ver_todas')
                and self.request.user.tiene_permiso('grupos.ver'))

    def get_queryset(self):
        if self._es_supervisor():
            miembro_ids = _miembros_grupo(self.request.user)
            qs = Reserva.objects.filter(
                Q(event_type__host_id__in=miembro_ids) | Q(host_id__in=miembro_ids)
            ).select_related('event_type', 'host').distinct()
        else:
            qs = Reserva.objects.select_related('event_type', 'host')

        host_id = self.request.GET.get('host', '').strip()
        email   = self.request.GET.get('email', '').strip()
        estado  = self.request.GET.get('estado', '').strip()
        orden   = self.request.GET.get('orden', 'reciente')
        periodo = self.request.GET.get('periodo', '').strip()
        if host_id:
            qs = qs.filter(host_id=host_id)
        if email:
            qs = qs.filter(email_invitado__icontains=email)
        if estado in ('confirmada', 'cancelada'):
            qs = qs.filter(estado=estado)
        if periodo == 'proximas':
            qs = qs.filter(inicio_utc__gt=timezone.now())
        elif periodo == 'pasadas':
            qs = qs.filter(inicio_utc__lte=timezone.now())
        qs = qs.order_by('fecha_creacion') if orden == 'antiguo' else qs.order_by('-fecha_creacion')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        es_supervisor = self._es_supervisor()
        ctx['titulo'] = 'Reservas del grupo' if es_supervisor else 'Todas las reservas'
        if es_supervisor:
            miembro_ids = _miembros_grupo(self.request.user)
            ctx['hosts'] = User.objects.filter(pk__in=miembro_ids, is_active=True).order_by('email')
        else:
            ctx['hosts'] = User.objects.filter(is_active=True).order_by('email')
        ctx['filtro_host']    = self.request.GET.get('host', '')
        ctx['filtro_email']   = self.request.GET.get('email', '')
        ctx['filtro_estado']  = self.request.GET.get('estado', '')
        ctx['filtro_orden']   = self.request.GET.get('orden', 'reciente')
        ctx['filtro_periodo'] = self.request.GET.get('periodo', '')
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx


class ReservaEliminarView(RequierePermisoMixin, View):
    permiso_requerido = 'reservas.cancelar'

    def post(self, request, pk):
        qs = Reserva.objects.all() if request.user.tiene_permiso('reservas.ver_todas') else Reserva.objects.filter(host=request.user)
        reserva = get_object_or_404(qs, pk=pk)
        nombre = reserva.nombre_invitado
        eliminar_reserva(reserva)
        messages.success(request, f"Reserva de '{nombre}' eliminada.")
        volver = 'panel_reservas:reserva_admin_list' if request.user.tiene_permiso('reservas.ver_todas') else 'panel_reservas:reserva_list'
        return redirect(volver)


class ReservaCancelarView(RequierePermisoMixin, View):
    permiso_requerido = 'reservas.cancelar'

    def post(self, request, pk):
        if not request.user.tiene_permiso('reservas.ver_todas'):
            from calendario.grupos.utils import usuario_bloqueado
            if usuario_bloqueado(request.user, 'bloquear_cancelar_reservas', request):
                messages.error(request, 'Tu grupo no te autoriza para cancelar reservas.')
                return redirect('panel_reservas:reserva_detail', pk=pk)
        qs = Reserva.objects.all() if request.user.tiene_permiso('reservas.ver_todas') else Reserva.objects.filter(host=request.user)
        reserva = get_object_or_404(qs, pk=pk)
        from .models import CancelacionReserva
        cancelar_reserva(
            reserva,
            origen=CancelacionReserva.Origen.PANEL,
            usuario=request.user,
            detalle=request.user.email,
        )
        messages.success(request, f"Reserva de '{reserva.nombre_invitado}' cancelada.")
        return redirect('panel_reservas:reserva_detail', pk=pk)


class CancelacionesListView(LoginRequiredMixin, ListView):
    """
    Registro de quién canceló cada reserva y desde dónde.

    Nace del incidente del 20/08/2026: hubo una tanda de cancelaciones y no se
    pudo responder a "¿quién canceló esto?" porque los logs del contenedor se
    van en cada despliegue. Los closers no entran a la app —solo ven Google
    Calendar y sus correos—, así que cuando una reserva suya desaparece la
    respuesta no puede ser "lo hizo el sistema".

    Restringida por email en `CANCELACIONES_EMAILS_AUTORIZADOS`, no por el
    sistema de permisos, porque de momento la ve una sola persona.
    """
    model = CancelacionReserva
    template_name = 'pages/panel/reservas/cancelaciones.html'
    context_object_name = 'cancelaciones'
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        autorizados = getattr(settings, 'CANCELACIONES_EMAILS_AUTORIZADOS', [])
        if (request.user.email or '').lower() not in autorizados:
            raise PermissionDenied('Esta vista es privada.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = (CancelacionReserva.objects
              .select_related('reserva', 'reserva__host', 'reserva__event_type', 'usuario')
              .order_by('-creada_en'))
        email = (self.request.GET.get('email') or '').strip()
        if email:
            qs = qs.filter(reserva__email_invitado__icontains=email)
        origen = (self.request.GET.get('origen') or '').strip()
        if origen:
            qs = qs.filter(origen=origen)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['email'] = self.request.GET.get('email', '')
        ctx['origen'] = self.request.GET.get('origen', '')
        ctx['origenes'] = CancelacionReserva.Origen.choices
        base = CancelacionReserva.objects.all()
        ctx['total'] = base.count()
        ctx['ultimas_24h'] = base.filter(
            creada_en__gte=timezone.now() - timedelta(hours=24)
        ).count()
        ctx['por_origen'] = {
            valor: base.filter(origen=valor).count()
            for valor, _etiqueta in CancelacionReserva.Origen.choices
        }
        return ctx
