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
from . import embed
from .correos import enviar_confirmacion_host, enviar_confirmacion_invitado
from .exceptions import ReservaDuplicadaError, SlotNoDisponibleError
from .forms import BookingForm
from .models import Reserva
from .services import calcular_slots, calcular_slots_cacheado, cancelar_reserva, crear_reserva, reemplazar_reserva

# Listas fijas en español para formatear fechas: strftime('%A'/'%B') depende del
# locale del SO (inglés en producción).
_DIAS_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
_MESES_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


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


def _avisar_si_es_nueva(reserva):
    """Programa los correos de confirmación salvo que la reserva ya existiera.

    `crear_reserva` es idempotente ante un reenvío del mismo hueco: devuelve la
    reserva que ya estaba en vez de crear otra. Los correos de esa reserva
    salieron cuando se hizo de verdad, y repetirlos solo hace dudar de si se ha
    reservado una vez o dos.
    """
    if getattr(reserva, 'reutilizada', False):
        return
    transaction.on_commit(lambda: _enviar_correos_confirmacion(reserva.pk))


def _render_booking(request, ctx, invitado, event_type, status=200):
    """Pinta la página de reserva, ya sea la pública de siempre o la embebida.

    Con `invitado` a None es exactamente el render de antes. Con un alumno
    detrás, adapta el contexto para que la reserva salga a su nombre.

    Que la página se pueda pintar dentro del iframe depende del evento y no de
    si hay alumno: en transición el iframe carga también sin token, que es justo
    lo que permite desplegarlo en la academia sin cerrar antes el enlace.
    """
    embed.aplicar_embed(ctx, invitado, embed.token_de_request(request))
    resp = render(request, 'pages/public/booking/page.html', ctx, status=status)
    return embed.permitir_embebido(resp) if event_type.embebible else resp


def _identidad(form, invitado):
    """Nombre y email con los que se crea la reserva.

    Cuando la reserva viene de la academia mandan los del token: son lo que el
    LMS firmó. Los del formulario se ignoran a propósito —van en readonly, pero
    eso solo lo respeta un navegador— para que a nadie le sirva de nada
    compartir el enlace: la reserva queda siempre a nombre del alumno.
    """
    if invitado is None:
        return form.cleaned_data['nombre_invitado'], form.cleaned_data['email_invitado']
    return invitado['nombre'], invitado['email']


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


def _siguiente_mes(mes):
    """Primer día del mes siguiente a `mes` (que ya es un día-1)."""
    return (mes.replace(day=28) + timedelta(days=4)).replace(day=1)


def _mes_tiene_slots(event_type, tz_visitante, min_fecha, max_fecha, mes_base):
    """True si el mes `mes_base` tiene al menos un slot dentro de la ventana reservable."""
    ultimo_dia = _siguiente_mes(mes_base) - timedelta(days=1)
    desde = max(mes_base, min_fecha)
    hasta = min(ultimo_dia, max_fecha)
    if desde > hasta:
        return False
    for s in calcular_slots_cacheado(event_type, desde - timedelta(days=1), hasta + timedelta(days=1)):
        d = s.astimezone(tz_visitante).date()
        if desde <= d <= hasta:
            return True
    return False


def _primer_mes_con_slots(event_type, tz_visitante, min_fecha, max_fecha, mes_base):
    """Avanza desde `mes_base` al primer mes con disponibilidad, acotado por `max_fecha`.
    Si ningún mes de la ventana tiene slots, devuelve `mes_base` sin cambios (se queda
    en el mes actual mostrándolo vacío, como antes)."""
    mes_max = max_fecha.replace(day=1)
    mes = mes_base
    while mes <= mes_max:
        if _mes_tiene_slots(event_type, tz_visitante, min_fecha, max_fecha, mes):
            return mes
        mes = _siguiente_mes(mes)
    return mes_base


def _build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha_sel,
                        auto_avanzar=False, hoy_local=None):
    """Construye el contexto de calendario (grid + días con slots) para el template.
    Todas las fechas se agrupan en la TZ del visitante.

    `min_fecha` es el primer día reservable y `hoy_local` el día de hoy: coinciden
    en el rango rodante, pero con un rango de fechas que empieza en el futuro no,
    y ahí uno acota el calendario mientras el otro solo pinta el "hoy".

    Si `auto_avanzar` es True (solo en la primera carga, sin mes/fecha explícitos), y el
    mes base no tiene disponibilidad, se salta al primer mes que sí la tenga."""
    if hoy_local is None:
        hoy_local = min_fecha
    mes_min = min_fecha.replace(day=1)
    mes_max = max_fecha.replace(day=1)
    mes_base = max(mes_min, min(mes_max, mes_base))

    if auto_avanzar:
        mes_base = _primer_mes_con_slots(event_type, tz_visitante, min_fecha, max_fecha, mes_base)

    # Grid (semanas con lunes primero). La última fila se completa con los
    # primeros días del mes siguiente, que también son reservables: así los
    # últimos días del mes no obligan al visitante a pasar de mes.
    cal_obj = cal_module.Calendar(firstweekday=0)
    semanas = cal_obj.monthdatescalendar(mes_base.year, mes_base.month)
    fin_grid = semanas[-1][-1]
    fin_mes = _siguiente_mes(mes_base) - timedelta(days=1)

    # Días con slots en la cuadrícula visible. Pedimos ±1 día al servicio para no
    # perder slots que cruzan la frontera de día entre TZ del host y del visitante.
    desde = max(mes_base, min_fecha)
    hasta = min(fin_grid, max_fecha)
    dias_con_slots = set()
    if desde <= hasta:
        for s in calcular_slots(event_type, desde - timedelta(days=1), hasta + timedelta(days=1)):
            d = s.astimezone(tz_visitante).date()
            if desde <= d <= hasta:
                dias_con_slots.add(d)

    cal_semanas = []
    for semana in semanas:
        fila = []
        for d in semana:
            fila.append({
                'fecha': d,
                'en_mes': d.month == mes_base.month,
                # La cola sí se pinta (apagada si no tiene horas); el relleno
                # del principio se sigue ocultando, el mes arranca en el día 1.
                'es_cola': d > fin_mes,
                'es_hoy': d == hoy_local,
                'es_seleccionada': d == fecha_sel,
                'clickable': (
                    d >= mes_base
                    and min_fecha <= d <= max_fecha
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


def _calcular_slots_mes_json(event_type, tz_visitante, min_fecha, max_fecha, mes_str):
    try:
        mes_base = date.fromisoformat(mes_str + '-01') if mes_str else None
    except ValueError:
        mes_base = None
    if not mes_base:
        mes_base = min_fecha.replace(day=1)

    mes_min = min_fecha.replace(day=1)
    mes_max = max_fecha.replace(day=1)
    mes_base = max(mes_min, min(mes_max, mes_base))

    # Hasta el final de la cuadrícula, no del mes: la última fila incluye los
    # primeros días del mes siguiente y también deben traer sus slots.
    fin_grid = cal_module.Calendar(firstweekday=0).monthdatescalendar(
        mes_base.year, mes_base.month)[-1][-1]
    desde = max(mes_base, min_fecha)
    hasta = min(fin_grid, max_fecha)

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
        try:
            embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado:
            return JsonResponse({'error': 'acceso restringido'}, status=403)
        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)
        data = _calcular_slots_mes_json(
            event_type, tz_visitante, min_fecha, max_fecha,
            request.GET.get('mes', ''),
        )
        return JsonResponse(data)


class SlotsMesJSONTeamView(View):

    def get(self, request, slug_equipo):
        event_type = get_object_or_404(EventType, slug_equipo=slug_equipo, activo=True)
        try:
            embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado:
            return JsonResponse({'error': 'acceso restringido'}, status=403)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)
        data = _calcular_slots_mes_json(
            event_type, tz_visitante, min_fecha, max_fecha,
            request.GET.get('mes', ''),
        )
        return JsonResponse(data)


class BookingPageView(View):

    def get(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)

        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)

        fecha_str = request.GET.get('fecha', '')
        try:
            fecha = date.fromisoformat(fecha_str) if fecha_str else None
        except ValueError:
            fecha = None
        if fecha and (fecha < min_fecha or fecha > max_fecha):
            fecha = None

        mes_str = request.GET.get('mes', '')
        try:
            mes_base = date.fromisoformat(mes_str).replace(day=1) if mes_str else None
        except ValueError:
            mes_base = None
        if not mes_base:
            mes_base = fecha.replace(day=1) if fecha else min_fecha.replace(day=1)

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
            'min_fecha_iso': min_fecha.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_host': host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_action_url': reverse('public_booking:booking_submit', kwargs={'user_slug': host.slug, 'event_type_slug': event_type.slug}),
            'slots_url': reverse('public_booking:slots_mes_json', kwargs={'user_slug': host.slug, 'event_type_slug': event_type.slug}),
        }
        auto_avanzar = not request.GET.get('mes') and not fecha
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha,
                                       auto_avanzar=auto_avanzar, hoy_local=hoy_local))
        return _render_booking(request, ctx, invitado, event_type)


class BookingFormView(View):

    def post(self, request, user_slug, event_type_slug):
        host = get_object_or_404(User, slug=user_slug, is_active=True)
        event_type = get_object_or_404(EventType, host=host, slug=event_type_slug, activo=True)
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)
        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, host, event_type, form)
        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        nombre_final, email_final = _identidad(form, invitado)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=nombre_final,
                email_invitado=email_final,
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
                tracking={'url': form.cleaned_data.get('url', '')},
            )
        except ReservaDuplicadaError as e:
            return self._render_with_errors(request, host, event_type, form, duplicado=e.reserva_existente)
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, host, event_type, form)
        _avisar_si_es_nueva(reserva)
        return _redirect_confirmacion(event_type, reserva)

    def _render_with_errors(self, request, host, event_type, form, duplicado=None):
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_host = ZoneInfo(host.timezone)
        tz_visitante = _tz_visitante(request, tz_host)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)
        fecha = inicio.astimezone(tz_visitante).date() if inicio else min_fecha
        mes_base = fecha.replace(day=1)
        slots = _slots_dia_visitante(event_type, fecha, tz_visitante)

        ctx = {
            'host': host,
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': min_fecha.isoformat(),
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
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha,
                                       hoy_local=hoy_local))
        if duplicado is not None:
            ctx.update(_duplicado_ctx(duplicado, inicio, tz_visitante))
        return _render_booking(request, ctx, invitado, event_type, status=400 if not duplicado else 200)


def _duplicado_ctx(duplicado, inicio_nuevo_utc, tz_ref):
    # Ambas horas en la zona del visitante (tz_ref), igual que la grilla de slots,
    # para que coincidan con lo que la persona eligió (estilo Calendly).
    dup_local = duplicado.inicio_utc.astimezone(tz_ref)
    nuevo_local = inicio_nuevo_utc.astimezone(tz_ref) if inicio_nuevo_utc else None
    return {
        'mostrar_modal_duplicado': True,
        'duplicado': duplicado,
        'duplicado_inicio_dia': date_format(dup_local, r"l, j \d\e F"),
        'duplicado_inicio_hora': dup_local.strftime('%H:%M'),
        'duplicado_token': str(duplicado.confirmacion_token),
        'nuevo_inicio_dia': date_format(nuevo_local, r"l, j \d\e F") if nuevo_local else '',
        'nuevo_inicio_hora': nuevo_local.strftime('%H:%M') if nuevo_local else '',
        'tz_ciudad': str(tz_ref).split('/')[-1].replace('_', ' '),
    }


class TeamBookingPageView(View):

    def get(self, request, slug_equipo):
        event_type = get_object_or_404(EventType, slug_equipo=slug_equipo, activo=True)
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)

        fecha_str = request.GET.get('fecha', '')
        try:
            fecha = date.fromisoformat(fecha_str) if fecha_str else None
        except ValueError:
            fecha = None
        if fecha and (fecha < min_fecha or fecha > max_fecha):
            fecha = None

        mes_str = request.GET.get('mes', '')
        try:
            mes_base = date.fromisoformat(mes_str).replace(day=1) if mes_str else None
        except ValueError:
            mes_base = None
        if not mes_base:
            mes_base = fecha.replace(day=1) if fecha else min_fecha.replace(day=1)

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
            'min_fecha_iso': min_fecha.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_ref': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'is_team': True,
            'form_action_url': reverse('public_team:booking_submit', kwargs={'slug_equipo': event_type.slug_equipo}),
            'slots_url': reverse('public_team:slots_mes_json', kwargs={'slug_equipo': event_type.slug_equipo}),
            # Prefill desde query params — mismos nombres que usa el funnel
            # (name/email/phone/setter), para los links de reagendamiento que
            # genera el CRM directo a esta página (no pasan por /agenda/).
            'nombre_invitado': (request.GET.get('name') or '').strip(),
            'email_invitado': (request.GET.get('email') or '').strip(),
            'telefono_invitado': (request.GET.get('phone') or '').strip(),
            # El CRM nombra este parámetro `setter_pre_email` en los links que
            # genera (p.ej. lead_register_without_preschedule); el funnel lo
            # llama `setter`. Aceptamos los dos: acaba igual en Reserva.setter
            # y de ahí sale como `setter_pre_email` en el ingest del CRM.
            'setter': (request.GET.get('setter') or request.GET.get('setter_pre_email') or '').strip(),
        }
        auto_avanzar = not request.GET.get('mes') and not fecha
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha,
                                       auto_avanzar=auto_avanzar, hoy_local=hoy_local))
        return _render_booking(request, ctx, invitado, event_type)


class TeamBookingFormView(View):

    def post(self, request, slug_equipo):
        event_type = get_object_or_404(EventType, slug_equipo=slug_equipo, activo=True)
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)
        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, event_type, form)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        nombre_final, email_final = _identidad(form, invitado)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=nombre_final,
                email_invitado=email_final,
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
                tracking={
                    'url': form.cleaned_data.get('url', ''),
                    'setter': form.cleaned_data.get('setter', ''),
                },
            )
        except ReservaDuplicadaError as e:
            return self._render_with_errors(request, event_type, form, duplicado=e.reserva_existente)
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, event_type, form)
        _avisar_si_es_nueva(reserva)
        return _redirect_confirmacion(event_type, reserva)

    def _render_with_errors(self, request, event_type, form, duplicado=None):
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)
        fecha = inicio.astimezone(tz_visitante).date() if inicio else min_fecha
        mes_base = fecha.replace(day=1)
        slots = _slots_dia_visitante(event_type, fecha, tz_visitante)

        ctx = {
            'event_type': event_type,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': min_fecha.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': _slots_template(slots, tz_visitante),
            'tz_ref': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_errors': form.errors,
            'nombre_invitado': request.POST.get('nombre_invitado', ''),
            'email_invitado': request.POST.get('email_invitado', ''),
            'telefono_invitado': request.POST.get('telefono_invitado', ''),
            'setter': request.POST.get('setter', ''),
            'notas': request.POST.get('notas', ''),
            'inicio_utc_str': request.POST.get('inicio_utc', ''),
            'slot_label': inicio.astimezone(tz_visitante).strftime('%H:%M') + ' h' if inicio else '',
            'is_team': True,
            'form_action_url': reverse('public_team:booking_submit', kwargs={'slug_equipo': event_type.slug_equipo}),
            'slots_url': reverse('public_team:slots_mes_json', kwargs={'slug_equipo': event_type.slug_equipo}),
        }
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha,
                                       hoy_local=hoy_local))
        if duplicado is not None:
            ctx.update(_duplicado_ctx(duplicado, inicio, tz_visitante))
        return _render_booking(request, ctx, invitado, event_type, status=400 if not duplicado else 200)


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
    """Cancelación desde el enlace de los correos (confirmación y recordatorio).

    El GET NO cancela: enseña una página de confirmación con un botón que hace
    el POST. Es a propósito. El enlace viaja en un correo, y los clientes de
    correo y los antivirus abren solos los enlaces para previsualizarlos o
    escanearlos: si el GET cancelara, se cancelarían reservas sin que nadie
    tocara nada.
    """

    def get(self, request, token):
        reserva = get_object_or_404(
            Reserva.objects.select_related('event_type', 'host'),
            confirmacion_token=token,
        )
        tz_display_str = reserva.timezone_invitado or reserva.host.timezone
        try:
            tz_display = ZoneInfo(tz_display_str)
        except Exception:
            tz_display = ZoneInfo(reserva.host.timezone)
        inicio_local = reserva.inicio_utc.astimezone(tz_display)
        ctx = {
            'reserva': reserva,
            'ya_cancelada': reserva.estado != Reserva.Estado.CONFIRMADA,
            'inicio_hora_str': f"{inicio_local.hour}:{inicio_local.minute:02d}",
            'inicio_fecha_str': (
                f"{_DIAS_ES[inicio_local.weekday()]}, "
                f"{inicio_local.day} de {_MESES_ES[inicio_local.month - 1]} "
                f"de {inicio_local.year}"
            ),
            'tz_display': tz_display_str,
        }
        return render(request, 'pages/public/booking/cancelar_confirmar.html', ctx)

    def post(self, request, token):
        reserva = get_object_or_404(Reserva, confirmacion_token=token)
        from .models import CancelacionReserva
        cancelar_reserva(
            reserva,
            origen=CancelacionReserva.Origen.PUBLICA,
            detalle=reserva.email_invitado,
        )
        return render(request, 'pages/public/booking/cancelada.html', {'reserva': reserva})


class ConfirmarAsistenciaPublicaView(View):
    """Botón "Confirmar asistencia" de los correos.

    No toca Google Calendar: el invitado ya se inserta como attendee
    'accepted' al crear el evento (ver google_calendar/services.py), así que
    para Google la asistencia nunca estuvo en duda. Esto solo deja constancia
    de que el invitado abrió el correo y dijo que va.

    A diferencia de cancelar, aquí el GET sí marca: la acción no destruye nada
    y es idempotente, y el invitado espera un solo clic. El coste es que un
    antivirus que abra el enlace para escanearlo marca la asistencia sin que
    el invitado toque nada, así que este dato vale como señal, no como prueba.
    """

    def get(self, request, token):
        reserva = get_object_or_404(
            Reserva.objects.select_related('event_type', 'host'),
            confirmacion_token=token,
        )
        cancelada = reserva.estado != Reserva.Estado.CONFIRMADA
        ya_estaba = reserva.asistencia_confirmada

        if not cancelada and not ya_estaba:
            reserva.asistencia_confirmada = True
            reserva.asistencia_confirmada_en = dj_timezone.now()
            reserva.save(update_fields=['asistencia_confirmada', 'asistencia_confirmada_en'])

        return render(request, 'pages/public/booking/asistencia_confirmada.html', {
            'reserva': reserva,
            'cancelada': cancelada,
            'ya_estaba': ya_estaba,
        })


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
        # En un evento «solo alumnos» la identidad no se puede cambiar al
        # reagendar: se conserva la de la reserva original. A esta vista se llega
        # con el enlace del correo, no con el token del LMS, así que el
        # formulario sería la única fuente; dejarlo mandar permitiría regalarle
        # la clase a alguien de fuera de la academia con un POST a mano.
        if vieja.event_type.solo_alumnos:
            nombre_final, email_final = vieja.nombre_invitado, vieja.email_invitado
        else:
            nombre_final = form.cleaned_data['nombre_invitado']
            email_final = form.cleaned_data['email_invitado']
        try:
            nueva = reemplazar_reserva(
                reserva_vieja_pk=vieja.pk,
                event_type=vieja.event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=nombre_final,
                email_invitado=email_final,
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
            )
        except SlotNoDisponibleError:
            # El slot nuevo se llenó entre que vio el modal y aceptó. Volvemos al confirmation
            # de la vieja para que pruebe otro horario.
            return redirect('public_token:confirmacion', token=vieja.confirmacion_token)

        _avisar_si_es_nueva(nueva)
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
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)

        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)

        fecha_str = request.GET.get('fecha', '')
        try:
            fecha = date.fromisoformat(fecha_str) if fecha_str else None
        except ValueError:
            fecha = None
        if fecha and (fecha < min_fecha or fecha > max_fecha):
            fecha = None

        mes_str = request.GET.get('mes', '')
        try:
            mes_base = date.fromisoformat(mes_str).replace(day=1) if mes_str else None
        except ValueError:
            mes_base = None
        if not mes_base:
            mes_base = fecha.replace(day=1) if fecha else min_fecha.replace(day=1)

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
            'min_fecha_iso': min_fecha.isoformat(),
            'max_fecha_iso': max_fecha.isoformat(),
            'slots_local': slots_local,
            'tz_host': event_type.host.timezone,
            'tz_visitante': str(tz_visitante),
            'hoy': hoy_local,
            'form_action_url': reverse('public_enlace_unico:booking_submit', kwargs={'token': token}),
            'slots_url': reverse('public_enlace_unico:slots_mes_json', kwargs={'token': token}),
        }
        auto_avanzar = not request.GET.get('mes') and not fecha
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha,
                                       auto_avanzar=auto_avanzar, hoy_local=hoy_local))
        return _render_booking(request, ctx, invitado, event_type)


class EnlaceUnicoFormView(View):

    def post(self, request, token):
        enlace = get_object_or_404(EnlaceUnico, token=token)
        if enlace.usado:
            return render(request, 'pages/public/booking/enlace_expirado.html', status=410)

        event_type = enlace.event_type
        if not event_type.activo:
            return render(request, 'pages/public/booking/enlace_expirado.html', status=410)
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)

        form = BookingForm(request.POST)
        if not form.is_valid():
            return self._render_with_errors(request, enlace, event_type, form)

        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        nombre_final, email_final = _identidad(form, invitado)
        try:
            reserva = crear_reserva(
                event_type=event_type,
                inicio_utc=form.cleaned_data['inicio_utc'],
                nombre_invitado=nombre_final,
                email_invitado=email_final,
                telefono_invitado=form.cleaned_data.get('telefono_invitado', ''),
                notas=form.cleaned_data.get('notas', ''),
                timezone_invitado=str(tz_visitante),
                tracking={'url': form.cleaned_data.get('url', '')},
            )
        except ReservaDuplicadaError as e:
            return self._render_with_errors(request, enlace, event_type, form, duplicado=e.reserva_existente)
        except SlotNoDisponibleError as e:
            form.add_error(None, str(e))
            return self._render_with_errors(request, enlace, event_type, form)

        enlace.usado = True
        enlace.usado_en = dj_timezone.now()
        enlace.save(update_fields=['usado', 'usado_en'])

        _avisar_si_es_nueva(reserva)
        return _redirect_confirmacion(event_type, reserva)

    def _render_with_errors(self, request, enlace, event_type, form, duplicado=None):
        try:
            invitado = embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado as e:
            return embed.respuesta_denegada(request, e)
        inicio = form.cleaned_data.get('inicio_utc') if form.is_bound and form.cleaned_data else None
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)
        fecha = inicio.astimezone(tz_visitante).date() if inicio else min_fecha
        mes_base = fecha.replace(day=1)
        slots = _slots_dia_visitante(event_type, fecha, tz_visitante)
        token = str(enlace.token)

        ctx = {
            'event_type': event_type,
            'host': event_type.host,
            'fecha': fecha,
            'fecha_iso': fecha.isoformat(),
            'min_fecha_iso': min_fecha.isoformat(),
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
        ctx.update(_build_calendar_ctx(event_type, tz_visitante, min_fecha, mes_base, max_fecha, fecha,
                                       hoy_local=hoy_local))
        if duplicado is not None:
            ctx.update(_duplicado_ctx(duplicado, inicio, tz_visitante))
        return _render_booking(request, ctx, invitado, event_type, status=400 if not duplicado else 200)


class EnlaceUnicoSlotsView(View):

    def get(self, request, token):
        enlace = get_object_or_404(EnlaceUnico, token=token)
        if enlace.usado:
            return JsonResponse({'error': 'enlace expirado'}, status=410)

        event_type = enlace.event_type
        try:
            embed.invitado_de_request(request, event_type)
        except embed.AccesoDenegado:
            return JsonResponse({'error': 'acceso restringido'}, status=403)
        tz_ref = ZoneInfo(event_type.host.timezone)
        tz_visitante = _tz_visitante(request, tz_ref)
        hoy_local = datetime.now(tz_visitante).date()
        min_fecha, max_fecha = event_type.ventana_reservas(hoy_local)
        data = _calcular_slots_mes_json(
            event_type, tz_visitante, min_fecha, max_fecha,
            request.GET.get('mes', ''),
        )
        return JsonResponse(data)
