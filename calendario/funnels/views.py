import json
import logging
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from calendario.bookings.exceptions import ReservaDuplicadaError, SlotNoDisponibleError
from calendario.bookings.services import crear_reserva
from calendario.bookings.views_public import _enviar_correos_confirmacion
from .models import FunnelForm, Prellamada
from .scoring import resolver_outcome

logger = logging.getLogger(__name__)


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {}


@method_decorator(csrf_exempt, name='dispatch')
class ConfigView(View):
    """GET /f/api/<slug>/config/ → bloques del formulario (sin scoring secrets)."""

    def get(self, request, slug):
        funnel = get_object_or_404(FunnelForm, slug=slug, activo=True)
        cfg = funnel.config or {}
        data = {
            'blocks': cfg.get('blocks', []),
            'q_order': cfg.get('q_order', []),
            'settings': cfg.get('settings', {}),
            'theme': cfg.get('theme', {}),
            'messages': cfg.get('messages', {}),
        }
        return JsonResponse(data)


@method_decorator(csrf_exempt, name='dispatch')
class ResolverView(View):
    """POST /f/api/<slug>/resolver/ → calcula outcome, crea Prellamada."""

    def post(self, request, slug):
        funnel = get_object_or_404(FunnelForm, slug=slug, activo=True)
        body = _json_body(request)
        respuestas = body.get('respuestas') or {}
        tracking = body.get('tracking') or {}

        outcome = resolver_outcome(funnel, respuestas)

        nombre = respuestas.get('name', '') or respuestas.get('nombre', '')
        email = respuestas.get('email', '')
        telefono = respuestas.get('phone', '') or respuestas.get('telefono', '')

        prellamada_kwargs = dict(
            funnel=funnel,
            nombre=nombre,
            email=email,
            telefono=telefono,
            respuestas=respuestas,
            score=outcome['promedio'] if outcome['promedio'] else None,
            resultado=outcome['resultado'],
            tracking=tracking,
        )
        if outcome['resultado'] == 'calendario':
            from calendario.event_types.models import EventType
            event_type = EventType.objects.filter(
                slug=outcome['event_type_slug'], activo=True
            ).first()
            prellamada_kwargs['event_type'] = event_type

        prellamada = Prellamada.objects.create(**prellamada_kwargs)

        if outcome['resultado'] == 'rechazado':
            return JsonResponse({
                'resultado': 'rechazado',
                'cancel_screen': outcome.get('cancel_screen', {}),
                'prellamada_token': str(prellamada.token),
            })

        evento_info = {}
        if event_type:
            evento_info = {
                'nombre': event_type.nombre,
                'duracion_minutos': event_type.duracion_minutos,
                'descripcion': event_type.descripcion or '',
                'precio': str(event_type.precio) if event_type.precio else None,
            }

        return JsonResponse({
            'resultado': 'calendario',
            'event_type_slug': outcome['event_type_slug'],
            'host_slug': outcome['host_slug'],
            'evento_info': evento_info,
            'prefill': {
                'nombre': nombre,
                'email': email,
                'telefono': telefono,
            },
            'prellamada_token': str(prellamada.token),
        })


@method_decorator(csrf_exempt, name='dispatch')
class ReservarView(View):
    """POST /f/api/<slug>/reservar/ → crea Reserva, vincula Prellamada, envía correos."""

    def post(self, request, slug):
        get_object_or_404(FunnelForm, slug=slug, activo=True)
        body = _json_body(request)

        token = body.get('prellamada_token', '')
        inicio_utc_str = body.get('inicio_utc', '')
        tz = body.get('tz', 'UTC')
        nombre = (body.get('nombre') or '').strip()
        email = (body.get('email') or '').strip()
        telefono = (body.get('telefono') or '').strip()
        notas = (body.get('notas') or '').strip()

        if not token:
            return JsonResponse({'ok': False, 'error': 'prellamada_token requerido.'}, status=400)
        if not inicio_utc_str:
            return JsonResponse({'ok': False, 'error': 'inicio_utc requerido.'}, status=400)
        if not nombre or not email:
            return JsonResponse({'ok': False, 'error': 'nombre y email requeridos.'}, status=400)

        try:
            prellamada = Prellamada.objects.select_related('event_type').get(token=token)
        except Prellamada.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Token inválido.'}, status=404)

        if prellamada.resultado != Prellamada.Resultado.CALENDARIO:
            return JsonResponse({'ok': False, 'error': 'Esta prellamada no tiene calendario asignado.'}, status=400)

        event_type = prellamada.event_type
        if event_type is None or not event_type.activo:
            return JsonResponse({'ok': False, 'error': 'El tipo de evento no está disponible.'}, status=400)

        inicio_utc_str_clean = inicio_utc_str.replace('Z', '+00:00')
        inicio_utc = parse_datetime(inicio_utc_str_clean)
        if inicio_utc is None:
            return JsonResponse({'ok': False, 'error': 'Formato de inicio_utc inválido.'}, status=400)
        if inicio_utc.tzinfo is None:
            inicio_utc = inicio_utc.replace(tzinfo=dt_timezone.utc)

        try:
            with transaction.atomic():
                reserva = crear_reserva(
                    event_type=event_type,
                    inicio_utc=inicio_utc,
                    nombre_invitado=nombre,
                    email_invitado=email,
                    telefono_invitado=telefono,
                    notas=notas,
                    timezone_invitado=tz,
                )
                prellamada.reserva = reserva
                prellamada.save(update_fields=['reserva'])
                r_pk = reserva.pk
                transaction.on_commit(lambda: _enviar_correos_confirmacion(r_pk))
        except ReservaDuplicadaError as e:
            existing = e.reserva_existente
            return JsonResponse({
                'ok': False,
                'error': 'duplicado',
                'mensaje': 'Ya tienes una reserva futura para este evento.',
                'reserva_existente': {
                    'confirmacion_token': str(existing.confirmacion_token),
                    'inicio_utc': existing.inicio_utc.isoformat(),
                },
            }, status=409)
        except SlotNoDisponibleError as e:
            return JsonResponse({'ok': False, 'error': 'slot_no_disponible', 'mensaje': str(e)}, status=409)

        return JsonResponse({
            'ok': True,
            'confirmacion_token': str(reserva.confirmacion_token),
        })


class FunnelPageView(View):
    """GET /f/<slug>/ → plantilla mínima (placeholder; React real en Paso 6+)."""

    def get(self, request, slug):
        funnel = get_object_or_404(FunnelForm, slug=slug, activo=True)
        return render(request, 'pages/public/funnel/page.html', {'funnel': funnel, 'slug': slug})
