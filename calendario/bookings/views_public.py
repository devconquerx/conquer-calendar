import calendar as cal_module
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from calendario.event_types.models import EventType
from calendario.users.models import User
from .exceptions import SlotNoDisponibleError
from .forms import BookingForm
from .models import Reserva
from .services import calcular_slots, cancelar_reserva, crear_reserva


def _build_calendar_ctx(event_type, tz_host, hoy_local, mes_base, max_fecha, fecha_sel):
    """Construye el contexto de calendario (grid + días con slots) para el template."""
    mes_min = hoy_local.replace(day=1)
    mes_max = max_fecha.replace(day=1)
    mes_base = max(mes_min, min(mes_max, mes_base))

    # Días con slots en el mes visible
    ultimo_dia = (mes_base.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    desde = max(mes_base, hoy_local)
    hasta = min(ultimo_dia, max_fecha)
    dias_con_slots = set()
    if desde <= hasta:
        for s in calcular_slots(event_type, desde, hasta):
            dias_con_slots.add(s.astimezone(tz_host).date())

    # Grid (semanas con domingo primero)
    cal_obj = cal_module.Calendar(firstweekday=6)
    cal_semanas = []
    for semana in cal_obj.monthdatescalendar(mes_base.year, mes_base.month):
        fila = []
        for d in semana:
            fila.append({
                'fecha': d,
                'en_mes': d.month == mes_base.month,
                'es_hoy': d == hoy_local,
                'es_seleccionada': d == fecha_sel,
                'clickable': (
                    d.month == mes_base.month
                    and hoy_local <= d <= max_fecha
                    and d in dias_con_slots
                ),
            })
        cal_semanas.append(fila)

    mes_anterior = (mes_base - timedelta(days=1)).replace(day=1)
    mes_siguiente = (mes_base.replace(day=28) + timedelta(days=4)).replace(day=1)

    return {
        'mes_base': mes_base,
        'cal_semanas': cal_semanas,
        'mes_anterior': mes_anterior if mes_anterior >= mes_min else None,
        'mes_siguiente': mes_siguiente if mes_siguiente <= mes_max else None,
    }


class BookingPageView(View):

    def get(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)

        tz_host = ZoneInfo(host.timezone)
        hoy_local = datetime.now(tz_host).date()
        max_fecha = hoy_local + timedelta(days=60)

        fecha_str = request.GET.get('fecha', '')
        try:
            fecha = date.fromisoformat(fecha_str) if fecha_str else None
        except ValueError:
            fecha = None
        if fecha and (fecha < hoy_local or fecha > max_fecha):
            fecha = None

        mes_str = request.GET.get('mes', '')
        try:
            mes_base = date.fromisoformat(mes_str).replace(day=1) if mes_str else None
        except ValueError:
            mes_base = None
        if not mes_base:
            mes_base = fecha.replace(day=1) if fecha else hoy_local.replace(day=1)

        slots_local = []
        if fecha:
            slots_local = [(s, s.astimezone(tz_host)) for s in calcular_slots(event_type, fecha, fecha)]

        ctx = {
            'host': host,
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat() if fecha else '',
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_host': host.timezone,
            'hoy': hoy_local,
        }
        ctx.update(_build_calendar_ctx(event_type, tz_host, hoy_local, mes_base, max_fecha, fecha))
        return render(request, 'pages/public/booking/page.html', ctx)


class BookingFormView(View):

    def post(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)
        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, host, event_type, form)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=form.cleaned_data['nombre_invitado'],
                email_invitado=form.cleaned_data['email_invitado'],
                notas=form.cleaned_data.get('notas', ''),
            )
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, host, event_type, form)
        return redirect('public_token:confirmacion', token=reserva.confirmacion_token)

    def _render_with_errors(self, request, host, event_type, form):
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_host = ZoneInfo(host.timezone)
        hoy_local = datetime.now(tz_host).date()
        max_fecha = hoy_local + timedelta(days=60)
        fecha = inicio.astimezone(tz_host).date() if inicio else hoy_local
        mes_base = fecha.replace(day=1)
        slots = calcular_slots(event_type, fecha, fecha)

        ctx = {
            'host': host,
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': [(s, s.astimezone(tz_host)) for s in slots],
            'tz_host': host.timezone,
            'hoy': hoy_local,
            'form_errors': form.errors,
            'nombre_invitado': request.POST.get('nombre_invitado', ''),
            'email_invitado': request.POST.get('email_invitado', ''),
            'notas': request.POST.get('notas', ''),
            'inicio_utc_str': request.POST.get('inicio_utc', ''),
            'slot_label': inicio.astimezone(tz_host).strftime('%H:%M') + ' h' if inicio else '',
        }
        ctx.update(_build_calendar_ctx(event_type, tz_host, hoy_local, mes_base, max_fecha, fecha))
        return render(request, 'pages/public/booking/page.html', ctx, status=400)


class ConfirmacionView(View):

    def get(self, request, token):
        reserva = get_object_or_404(
            Reserva.objects.select_related('event_type', 'host'),
            confirmacion_token=token,
        )
        tz_host = ZoneInfo(reserva.host.timezone)
        inicio_local = reserva.inicio_utc.astimezone(tz_host)
        fin_local = (reserva.inicio_utc + timedelta(minutes=reserva.event_type.duracion_minutos)).astimezone(tz_host)
        ctx = {
            'reserva': reserva,
            'inicio_local': inicio_local,
            'fin_local': fin_local,
            'tz_host': reserva.host.timezone,
        }
        return render(request, 'pages/public/booking/confirmacion.html', ctx)


class CancelarPublicaView(View):

    def post(self, request, token):
        reserva = get_object_or_404(Reserva, confirmacion_token=token)
        cancelar_reserva(reserva)
        return render(request, 'pages/public/booking/cancelada.html', {'reserva': reserva})
