import calendar as cal_module
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.formats import date_format
from django.views import View

from django.utils import timezone as dj_timezone
from django.urls import reverse

from calendario.event_types.models import EventType, EnlaceUnico
from calendario.users.models import User
from .correos import enviar_confirmacion_host, enviar_confirmacion_invitado
from .exceptions import ReservaDuplicadaError, SlotNoDisponibleError
from .forms import BookingForm
from .models import Reserva
from .services import calcular_slots, calcular_slots_cacheado, cancelar_reserva, crear_reserva, reemplazar_reserva


def _redirect_confirmacion(event_type, reserva):
    if event_type.confirmacion_tipo == 'url' and event_type.confirmacion_url:
        return redirect(event_type.confirmacion_url)
    return redirect('public_token:confirmacion', token=reserva.confirmacion_token)


def _enviar_correos_confirmacion(reserva_pk):
    """Envía correos de confirmación con la reserva ya refrescada de BD (google_event_id poblado)."""
    try:
        r = Reserva.objects.get(pk=reserva_pk)
    except Reserva.DoesNotExist:
        return
    enviar_confirmacion_host(r)
    enviar_confirmacion_invitado(r)


def _tz_visitante(request, tz_fallback):
    """Lee tz de query/form y devuelve ZoneInfo válido o el fallback (TZ del host)."""
    raw = (request.GET.get('tz') or request.POST.get('tz') or '').strip()
    if not raw:
        return tz_fallback
    try:
        return ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError):
        return tz_fallback


def _slots_dia_visitante(event_type, fecha, tz_visitante):
    """Slots cuyo inicio_utc cae dentro de [fecha 00:00 tz_visitante, +24h).
    Pide ±1 día al servicio para cubrir el solape entre TZ visitante y TZ host."""
    inicio_dia_utc = datetime.combine(fecha, datetime.min.time(), tzinfo=tz_visitante)
    fin_dia_utc = inicio_dia_utc + timedelta(days=1)
    crudos = calcular_slots(event_type, fecha - timedelta(days=1), fecha + timedelta(days=1))
    return [s for s in crudos if inicio_dia_utc <= s < fin_dia_utc]


def _slots_template(slots_utc, tz_visitante):
    """Pre-formatea (utc_iso, 'HH:MM') para que el filtro |date del template
    no re-convierta a la TIME_ZONE de Django y rompa la TZ del visitante."""
    return [
        (s.isoformat(), s.astimezone(tz_visitante).strftime('%H:%M'))
        for s in slots_utc
    ]


def _build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha_sel):
    """Construye el contexto de calendario (grid + días con slots) para el template.
    Todas las fechas se agrupan en la TZ del visitante."""
    mes_min = hoy_local.replace(day=1)
    mes_max = max_fecha.replace(day=1)
    mes_base = max(mes_min, min(mes_max, mes_base))

    # Días con slots en el mes visible. Pedimos ±1 día al servicio para no
    # perder slots que cruzan la frontera de día entre TZ del host y del visitante.
    ultimo_dia = (mes_base.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    desde = max(mes_base, hoy_local)
    hasta = min(ultimo_dia, max_fecha)
    dias_con_slots = set()
    if desde <= hasta:
        for s in calcular_slots(event_type, desde - timedelta(days=1), hasta + timedelta(days=1)):
            d = s.astimezone(tz_visitante).date()
            if desde <= d <= hasta:
                dias_con_slots.add(d)

    # Grid (semanas con lunes primero)
    cal_obj = cal_module.Calendar(firstweekday=0)
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


def _calcular_slots_mes_json(event_type, tz_visitante, hoy_local, max_fecha, mes_str):
    try:
        mes_base = date.fromisoformat(mes_str + '-01') if mes_str else None
    except ValueError:
        mes_base = None
    if not mes_base:
        mes_base = hoy_local.replace(day=1)

    mes_min = hoy_local.replace(day=1)
    mes_max = max_fecha.replace(day=1)
    mes_base = max(mes_min, min(mes_max, mes_base))

    ultimo_dia = (mes_base.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    desde = max(mes_base, hoy_local)
    hasta = min(ultimo_dia, max_fecha)

    mes_anterior = (mes_base - timedelta(days=1)).replace(day=1)
    mes_siguiente = (mes_base.replace(day=28) + timedelta(days=4)).replace(day=1)

    dias = {}
    utcs = {}
    if desde <= hasta:
        slots_mes = calcular_slots_cacheado(
            event_type,
            desde - timedelta(days=1),
            hasta + timedelta(days=1),
        )
        for s in slots_mes:
            d = s.astimezone(tz_visitante).date()
            if desde <= d <= hasta:
                key = d.isoformat()
                dias.setdefault(key, []).append(s.astimezone(tz_visitante).strftime('%H:%M'))
                utcs.setdefault(key, []).append(s.isoformat())

    return {
        'dias': dias,
        'slots_utc': utcs,
        'mes': mes_base.isoformat(),
        'mes_anterior': mes_anterior.isoformat() if mes_anterior >= mes_min else None,
        'mes_siguiente': mes_siguiente.isoformat() if mes_siguiente <= mes_max else None,
        'max_fecha': max_fecha.isoformat(),
    }


class SlotsMesJSONView(View):

    def get(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)
        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)
        data = _calcular_slots_mes_json(
            event_type, tz_visitante, hoy_local, max_fecha,
            request.GET.get('mes', ''),
        )
        return JsonResponse(data)


class SlotsMesJSONTeamView(View):

    def get(self, request, slug_equipo):
        event_type = get_object_or_404(EventType, slug_equipo=slug_equipo, activo=True)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)
        data = _calcular_slots_mes_json(
            event_type, tz_visitante, hoy_local, max_fecha,
            request.GET.get('mes', ''),
        )
        return JsonResponse(data)


class BookingPageView(View):

    def get(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)

        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)

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
            slots_local = _slots_template(
                _slots_dia_visitante(event_type, fecha, tz_visitante),
                tz_visitante,
            )

        ctx = {
            'host': host,
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat() if fecha else '',
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_host': host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_action_url': reverse('public_booking:booking_submit', kwargs={'user_slug': host.slug, 'event_type_slug': event_type.slug}),
            'slots_url': reverse('public_booking:slots_mes_json', kwargs={'user_slug': host.slug, 'event_type_slug': event_type.slug}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha))
        return render(request, 'pages/public/booking/page.html', ctx)


class BookingFormView(View):

    def post(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)
        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, host, event_type, form)
        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=form.cleaned_data['nombre_invitado'],
                email_invitado=form.cleaned_data['email_invitado'],
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
            )
        except ReservaDuplicadaError as e:
            return self._render_with_errors(request, host, event_type, form, duplicado=e.reserva_existente)
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, host, event_type, form)
        transaction.on_commit(lambda: _enviar_correos_confirmacion(reserva.pk))
        return _redirect_confirmacion(event_type, reserva)

    def _render_with_errors(self, request, host, event_type, form, duplicado=None):
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)
        fecha = inicio.astimezone(tz_visitante).date() if inicio else hoy_local
        mes_base = fecha.replace(day=1)
        slots = _slots_dia_visitante(event_type, fecha, tz_visitante)

        ctx = {
            'host': host,
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': _slots_template(slots, tz_visitante),
            'tz_host': host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_errors': form.errors,
            'nombre_invitado': request.POST.get('nombre_invitado', ''),
            'email_invitado': request.POST.get('email_invitado', ''),
            'telefono_invitado': request.POST.get('telefono_invitado', ''),
            'notas': request.POST.get('notas', ''),
            'inicio_utc_str': request.POST.get('inicio_utc', ''),
            'slot_label': inicio.astimezone(tz_visitante).strftime('%H:%M') + ' h' if inicio else '',
            'form_action_url': reverse('public_booking:booking_submit', kwargs={'user_slug': host.slug, 'event_type_slug': event_type.slug}),
            'slots_url': reverse('public_booking:slots_mes_json', kwargs={'user_slug': host.slug, 'event_type_slug': event_type.slug}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha))
        if duplicado is not None:
            ctx.update(_duplicado_ctx(duplicado, inicio, tz_visitante))
        return render(request, 'pages/public/booking/page.html', ctx, status=400 if not duplicado else 200)


def _duplicado_ctx(duplicado, inicio_nuevo_utc, tz_ref):
    tz_dup = ZoneInfo(duplicado.host.timezone)
    dup_local = duplicado.inicio_utc.astimezone(tz_dup)
    nuevo_local = inicio_nuevo_utc.astimezone(tz_ref) if inicio_nuevo_utc else None
    return {
        'mostrar_modal_duplicado': True,
        'duplicado': duplicado,
        'duplicado_inicio_dia': date_format(dup_local, r"l, j \d\e F"),
        'duplicado_inicio_hora': dup_local.strftime('%H:%M'),
        'duplicado_token': str(duplicado.confirmacion_token),
        'nuevo_inicio_dia': date_format(nuevo_local, r"j \d\e F") if nuevo_local else '',
        'nuevo_inicio_hora': nuevo_local.strftime('%H:%M') if nuevo_local else '',
    }


class TeamBookingPageView(View):

    def get(self, request, slug_equipo):
        event_type = get_object_or_404(EventType, slug_equipo=slug_equipo, activo=True)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)

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
            slots_local = _slots_template(
                _slots_dia_visitante(event_type, fecha, tz_visitante),
                tz_visitante,
            )

        ctx = {
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat() if fecha else '',
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_ref': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'is_team': True,
            'form_action_url': reverse('public_team:booking_submit', kwargs={'slug_equipo': event_type.slug_equipo}),
            'slots_url': reverse('public_team:slots_mes_json', kwargs={'slug_equipo': event_type.slug_equipo}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha))
        return render(request, 'pages/public/booking/page.html', ctx)


class TeamBookingFormView(View):

    def post(self, request, slug_equipo):
        event_type = get_object_or_404(EventType, slug_equipo=slug_equipo, activo=True)
        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, event_type, form)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=form.cleaned_data['nombre_invitado'],
                email_invitado=form.cleaned_data['email_invitado'],
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
            )
        except ReservaDuplicadaError as e:
            return self._render_with_errors(request, event_type, form, duplicado=e.reserva_existente)
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, event_type, form)
        transaction.on_commit(lambda: _enviar_correos_confirmacion(reserva.pk))
        return _redirect_confirmacion(event_type, reserva)

    def _render_with_errors(self, request, event_type, form, duplicado=None):
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)
        fecha = inicio.astimezone(tz_visitante).date() if inicio else hoy_local
        mes_base = fecha.replace(day=1)
        slots = _slots_dia_visitante(event_type, fecha, tz_visitante)

        ctx = {
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': _slots_template(slots, tz_visitante),
            'tz_ref': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_errors': form.errors,
            'nombre_invitado': request.POST.get('nombre_invitado', ''),
            'email_invitado': request.POST.get('email_invitado', ''),
            'telefono_invitado': request.POST.get('telefono_invitado', ''),
            'notas': request.POST.get('notas', ''),
            'inicio_utc_str': request.POST.get('inicio_utc', ''),
            'slot_label': inicio.astimezone(tz_visitante).strftime('%H:%M') + ' h' if inicio else '',
            'is_team': True,
            'form_action_url': reverse('public_team:booking_submit', kwargs={'slug_equipo': event_type.slug_equipo}),
            'slots_url': reverse('public_team:slots_mes_json', kwargs={'slug_equipo': event_type.slug_equipo}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha))
        if duplicado is not None:
            ctx.update(_duplicado_ctx(duplicado, inicio, tz_visitante))
        return render(request, 'pages/public/booking/page.html', ctx, status=400 if not duplicado else 200)


class ConfirmacionView(View):

    def get(self, request, token):
        reserva = get_object_or_404(
            Reserva.objects.select_related('event_type', 'host'),
            confirmacion_token=token,
        )
        # Mostrar la hora en la TZ que el visitante eligió al reservar.
        # Si la reserva es anterior al campo (default 'UTC'), se usa la TZ del host
        # como fallback razonable.
        tz_display_str = reserva.timezone_invitado or reserva.host.timezone
        try:
            tz_display = ZoneInfo(tz_display_str)
        except Exception:
            tz_display = ZoneInfo(reserva.host.timezone)
        inicio_local = reserva.inicio_utc.astimezone(tz_display)
        fin_local = (reserva.inicio_utc + timedelta(minutes=reserva.event_type.duracion_minutos)).astimezone(tz_display)
        # Pasamos strings pre-formateados para evitar que Django reconvierta
        # los datetimes a TIME_ZONE del servidor en el template (TIME_ZONE="Europe/Madrid").
        # Usamos listas fijas en español porque strftime('%A'/'%B') depende del
        # locale del SO (inglés en producción).
        _DIAS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        _MESES_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                     'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        ctx = {
            'reserva': reserva,
            'inicio_local': inicio_local,
            'fin_local': fin_local,
            'inicio_hora_str': f"{inicio_local.hour}:{inicio_local.minute:02d}",
            'fin_hora_str':    f"{fin_local.hour}:{fin_local.minute:02d}",
            'inicio_fecha_str': (
                f"{_DIAS_ES[inicio_local.weekday()]}, "
                f"{inicio_local.day} de {_MESES_ES[inicio_local.month - 1]} "
                f"de {inicio_local.year}"
            ),
            'tz_host': tz_display_str,
        }
        return render(request, 'pages/public/booking/confirmacion.html', ctx)


class CancelarPublicaView(View):

    def post(self, request, token):
        reserva = get_object_or_404(Reserva, confirmacion_token=token)
        cancelar_reserva(reserva)
        return render(request, 'pages/public/booking/cancelada.html', {'reserva': reserva})


class ReemplazarPublicaView(View):
    """Endpoint disparado por el modal de duplicado.

    Recibe el token de la reserva vieja + los datos del form de la nueva,
    cancela la vieja y crea la nueva (mismo event_type que la vieja).
    """

    def post(self, request, token):
        vieja = get_object_or_404(
            Reserva.objects.select_related('event_type', 'host'),
            confirmacion_token=token,
        )
        if vieja.estado != Reserva.Estado.CONFIRMADA:
            return redirect('public_token:confirmacion', token=vieja.confirmacion_token)

        form = BookingForm(request.POST)
        if not form.is_valid():
            return redirect('public_token:confirmacion', token=vieja.confirmacion_token)

        # Mantener la TZ que el visitante tenía al hacer la reserva original.
        # Si el modal lleva un campo tz en el POST se usaría ese; de lo contrario
        # se preserva el de la reserva vieja para no cambiarla sin querer.
        tz_visitante = _tz_visitante(request, ZoneInfo(vieja.timezone_invitado or vieja.host.timezone))
        try:
            nueva = reemplazar_reserva(
                reserva_vieja_pk=vieja.pk,
                event_type=vieja.event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=form.cleaned_data['nombre_invitado'],
                email_invitado=form.cleaned_data['email_invitado'],
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
            )
        except SlotNoDisponibleError:
            # El slot nuevo se llenó entre que vio el modal y aceptó. Volvemos al confirmation
            # de la vieja para que pruebe otro horario.
            return redirect('public_token:confirmacion', token=vieja.confirmacion_token)

        transaction.on_commit(lambda: _enviar_correos_confirmacion(nueva.pk))
        return _redirect_confirmacion(vieja.event_type, nueva)


# ── Enlace único de un solo uso ───────────────────────────────────────────────

class EnlaceUnicoPageView(View):

    def get(self, request, token):
        enlace = get_object_or_404(EnlaceUnico, token=token)
        if enlace.usado:
            return render(request, 'pages/public/booking/enlace_expirado.html', status=410)

        event_type = enlace.event_type
        if not event_type.activo:
            return render(request, 'pages/public/booking/enlace_expirado.html', status=410)

        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)

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
            slots_local = _slots_template(
                _slots_dia_visitante(event_type, fecha, tz_visitante),
                tz_visitante,
            )

        ctx = {
            'event_type': event_type,
            'host': event_type.host,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat() if fecha else '',
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_host': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_action_url': reverse('public_enlace_unico:booking_submit', kwargs={'token': token}),
            'slots_url': reverse('public_enlace_unico:slots_mes_json', kwargs={'token': token}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha))
        return render(request, 'pages/public/booking/page.html', ctx)


class EnlaceUnicoFormView(View):

    def post(self, request, token):
        enlace = get_object_or_404(EnlaceUnico, token=token)
        if enlace.usado:
            return render(request, 'pages/public/booking/enlace_expirado.html', status=410)

        event_type = enlace.event_type
        if not event_type.activo:
            return render(request, 'pages/public/booking/enlace_expirado.html', status=410)

        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, enlace, event_type, form)

        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=form.cleaned_data['nombre_invitado'],
                email_invitado=form.cleaned_data['email_invitado'],
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
            )
        except ReservaDuplicadaError as e:
            return self._render_with_errors(request, enlace, event_type, form, duplicado=e.reserva_existente)
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, enlace, event_type, form)

        enlace.usado = True
        enlace.usado_en = dj_timezone.now()
        enlace.save(update_fields=['usado', 'usado_en'])

        transaction.on_commit(lambda: _enviar_correos_confirmacion(reserva.pk))
        return _redirect_confirmacion(event_type, reserva)

    def _render_with_errors(self, request, enlace, event_type, form, duplicado=None):
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)
        fecha = inicio.astimezone(tz_visitante).date() if inicio else hoy_local
        mes_base = fecha.replace(day=1)
        slots = _slots_dia_visitante(event_type, fecha, tz_visitante)
        token = str(enlace.token)

        ctx = {
            'event_type': event_type,
            'host': event_type.host,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': hoy_local.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': _slots_template(slots, tz_visitante),
            'tz_host': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_errors': form.errors,
            'nombre_invitado': request.POST.get('nombre_invitado', ''),
            'email_invitado': request.POST.get('email_invitado', ''),
            'telefono_invitado': request.POST.get('telefono_invitado', ''),
            'notas': request.POST.get('notas', ''),
            'inicio_utc_str': request.POST.get('inicio_utc', ''),
            'slot_label': inicio.astimezone(tz_visitante).strftime('%H:%M') + ' h' if inicio else '',
            'form_action_url': reverse('public_enlace_unico:booking_submit', kwargs={'token': token}),
            'slots_url': reverse('public_enlace_unico:slots_mes_json', kwargs={'token': token}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, hoy_local, mes_base, max_fecha, fecha))
        if duplicado is not None:
            ctx.update(_duplicado_ctx(duplicado, inicio, tz_visitante))
        return render(request, 'pages/public/booking/page.html', ctx, status=400 if not duplicado else 200)


class EnlaceUnicoSlotsView(View):

    def get(self, request, token):
        enlace = get_object_or_404(EnlaceUnico, token=token)
        if enlace.usado:
            return JsonResponse({'error': 'enlace expirado'}, status=410)

        event_type = enlace.event_type
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        max_fecha = hoy_local + timedelta(days=event_type.aviso_maximo_dias)
        data = _calcular_slots_mes_json(
            event_type, tz_visitante, hoy_local, max_fecha,
            request.GET.get('mes', ''),
        )
        return JsonResponse(data)
