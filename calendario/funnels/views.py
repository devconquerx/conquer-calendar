import json
import logging
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse
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
            'escuela': funnel.escuela,
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
        # En modo Calendly el rango no resuelve EventType local (queda None); la
        # Prellamada se guarda igual (el evento se agenda en Calendly).
        event_type = None
        if outcome['resultado'] == 'calendario' and outcome.get('event_type_slug'):
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
            'calendly_url': outcome.get('calendly_url', ''),
            'event_type_slug': outcome.get('event_type_slug'),
            'host_slug': outcome.get('host_slug'),
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


# Producto (en la URL pública) → escuela (en BD). Las URLs canónicas por marca
# son /agenda/<producto>/<region>/. Añadir aquí nuevas marcas/productos.
PRODUCTO_A_ESCUELA = {
    'fullstack': 'conquer-blocks',
    'proptrading': 'conquer-finance',
    'english': 'conquer-languages',
    'legal': 'conquer-legal',
    'kids': 'conquer-languages-kids',
}
PRODUCTO_POR_ESCUELA = {v: k for k, v in PRODUCTO_A_ESCUELA.items()}


def _base_path(request):
    """Prefijo de path bajo el que se sirve el funnel (p.ej. /preview), o ''.

    Lo fija AppBasePathMiddleware. Las URLs de navegación que emiten las vistas
    lo anteponen para que el flujo encadenado permanezca dentro del prefijo.
    """
    return getattr(request, 'app_base_path', '')


def stepform_url(escuela, region, base=''):
    """URL pública canónica del StepForm: /agenda/<producto>/<region>/.

    `base` antepone un prefijo de path (p.ej. /preview) para mantener la
    navegación dentro del prefijo cuando el funnel se sirve detrás de él.
    """
    producto = PRODUCTO_POR_ESCUELA.get(escuela)
    if producto and region:
        return f'{base}/agenda/{producto}/{region}/'
    return ''


class FunnelAgendaView(View):
    """GET /agenda/<producto>/<region>/ → resuelve el funnel por escuela+región.

    URL pública por marca (ej. /agenda/fullstack/eu/). La API sigue siendo por
    slug (/f/api/<slug>/...): la plantilla recibe el slug del funnel resuelto.
    """

    def get(self, request, producto, region):
        escuela = PRODUCTO_A_ESCUELA.get(producto)
        funnel = get_object_or_404(
            FunnelForm, escuela=escuela, region=region, activo=True
        )
        from .context_processors import get_pixel_ids
        return render(
            request,
            'pages/public/funnel/page.html',
            {
                'funnel': funnel,
                'slug': funnel.slug,
                'pixel_ids': get_pixel_ids(funnel.escuela),
                'confirmation_url': confirmacion_url(funnel.escuela, funnel.region, base=_base_path(request)),
                'app_base_path': _base_path(request),
            },
        )


def _escuela_por_host(request):
    """Resuelve la escuela según el dominio (Host) usando settings.FUNNEL_HOST_ESCUELA.

    En dev (DEBUG) permite forzarla con ?escuela=conquer-languages para poder
    probar en localhost.
    """
    host = request.get_host().split(':')[0].lower().strip()
    mapping = getattr(settings, 'FUNNEL_HOST_ESCUELA', {}) or {}
    escuela = mapping.get(host)
    if not escuela and host.startswith('www.'):
        escuela = mapping.get(host[4:])
    if not escuela and settings.DEBUG:
        escuela = request.GET.get('escuela')
    return escuela


# Escuelas que llevan la escuela en el PATH (p.ej. /conquer-blocks/...). El resto
# comparte la ruta raíz y se resuelve por dominio (Host).
_ESCUELAS_RUTA_PATH = ('conquer-blocks', 'conquer-legal')


# URLs de la página de video por marca.
def _video_url(escuela, region, base=''):
    if escuela in _ESCUELAS_RUTA_PATH:
        return f'{base}/{escuela}/video-clase-{region}/'
    return f'{base}/video-clase-{region}/'


# URL de la página de confirmación de llamada por marca (misma convención).
def confirmacion_url(escuela, region, base=''):
    if escuela in _ESCUELAS_RUTA_PATH:
        return f'{base}/{escuela}/confirmacion-llamada-{region}/'
    return f'{base}/confirmacion-llamada-{region}/'


# URLs de video por defecto si el FunnelForm.config no trae 'video' (fail-safe).
_VIDEO_DEFAULTS = {
    'conquer-blocks': {
        'videoUrls': [
            'https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain-2025-compress.mp4',
            'https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain.mp4',
        ],
        'buttonPercent': 75,
    },
    # Conquer Legal aún no tiene VSL propia: reutiliza el vídeo de conquer-blocks
    # como plantilla temporal para que la landing encadene a la página de vídeo.
    'conquer-legal': {
        'videoUrls': [
            'https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain-2025-compress.mp4',
            'https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain.mp4',
        ],
        'buttonPercent': 75,
    },
}


# Plantillas de landing por marca (las que no estén aquí usan la landing React).
_LANDING_TEMPLATE_POR_ESCUELA = {
    'conquer-languages': 'pages/public/funnel/landing_languages.html',
}


class FunnelClaseView(View):
    """GET de las landings de registro de lead:

      - /conquer-blocks/clase-online-gratuita-<region>/  → escuela fija en el path
      - /clase-online-gratuita-<region>/                 → escuela resuelta por Host
        (conquerlanguages.* → conquer-languages, conquerfinance.* → conquer-finance)
    """

    def get(self, request, region, escuela=None):
        if escuela is None:
            escuela = _escuela_por_host(request)
        if not escuela:
            raise Http404('No se pudo resolver la escuela para este dominio.')
        funnel = get_object_or_404(
            FunnelForm, escuela=escuela, region=region, activo=True
        )
        from .context_processors import get_pixel_ids
        # Siguiente etapa tras la landing: la página de video si la marca la tiene
        # configurada; si no, directo al StepForm (/agenda/<producto>/<region>/).
        cfg = funnel.config or {}
        if cfg.get('video') or funnel.escuela in _VIDEO_DEFAULTS:
            next_url = _video_url(funnel.escuela, funnel.region, base=_base_path(request))
        else:
            next_url = stepform_url(funnel.escuela, funnel.region, base=_base_path(request))
        # Plantilla de landing por marca: languages tiene su propio diseño
        # (HTML + Tailwind) que replica conquerlanguages.com; el resto usa la
        # landing React por defecto.
        template_name = _LANDING_TEMPLATE_POR_ESCUELA.get(
            funnel.escuela, 'pages/public/funnel/landing.html',
        )
        return render(
            request,
            template_name,
            {
                'funnel': funnel,
                'slug': funnel.slug,
                'program': PRODUCTO_POR_ESCUELA.get(funnel.escuela, ''),
                'next_url': next_url,
                'landing_config': funnel.config or {},
                'pixel_ids': get_pixel_ids(funnel.escuela),
                'app_base_path': _base_path(request),
            },
        )


class FunnelVideoView(View):
    """GET de la página de video (VSL), entre la landing y el StepForm:

      - /conquer-blocks/video-clase-<region>/  → escuela fija en el path
      - /video-clase-<region>/                 → escuela resuelta por Host
    """

    def get(self, request, region, escuela=None):
        if escuela is None:
            escuela = _escuela_por_host(request)
        if not escuela:
            raise Http404('No se pudo resolver la escuela para este dominio.')
        funnel = get_object_or_404(
            FunnelForm, escuela=escuela, region=region, activo=True
        )
        from .context_processors import get_pixel_ids
        cfg = funnel.config or {}
        # La config del video (videoUrls + buttonPercent) vive en config['video'];
        # si falta, usamos los defaults por marca.
        video_cfg = dict(cfg)
        if not video_cfg.get('video'):
            video_cfg['video'] = _VIDEO_DEFAULTS.get(funnel.escuela, {})
        # Siguiente etapa tras el video: el StepForm (/agenda/<producto>/<region>/).
        next_url = stepform_url(funnel.escuela, funnel.region, base=_base_path(request))
        return render(
            request,
            'pages/public/funnel/video.html',
            {
                'funnel': funnel,
                'slug': funnel.slug,
                'next_url': next_url,
                'video_config': video_cfg,
                'pixel_ids': get_pixel_ids(funnel.escuela),
                'app_base_path': _base_path(request),
            },
        )


class FunnelConfirmationView(View):
    """GET de la página de confirmación de llamada (tras agendar en Calendly):

      - /conquer-blocks/confirmacion-llamada[-<region>]/  → escuela fija en el path
      - /confirmacion-llamada[-<region>]/                 → escuela resuelta por Host

    No depende de un FunnelForm concreto: solo necesita la escuela para el tema
    (conquerblocks) y los pixeles. Si la región viene en la URL se usa para
    resolver el funnel (título/pixeles); si no, se toma cualquiera activo de la
    escuela. Equivale a la ruta `confirmation` del funnel de Django.
    """

    def get(self, request, region=None, escuela=None):
        if escuela is None:
            escuela = _escuela_por_host(request)
        if not escuela:
            raise Http404('No se pudo resolver la escuela para este dominio.')
        funnel = None
        if region:
            funnel = FunnelForm.objects.filter(
                escuela=escuela, region=region, activo=True
            ).first()
        if funnel is None:
            funnel = FunnelForm.objects.filter(escuela=escuela, activo=True).first()
        from .context_processors import get_pixel_ids
        return render(
            request,
            'pages/public/funnel/confirmation.html',
            {
                'funnel': funnel,
                'escuela': escuela,
                'slug': funnel.slug if funnel else '',
                'region': region or (funnel.region if funnel else ''),
                'pixel_ids': get_pixel_ids(escuela),
                'app_base_path': _base_path(request),
            },
        )


class FunnelStatusView(View):
    """Panel de estado de los funnels.

    Lista cada escuela×región registrada con su estado (activo, ¿tiene landing?,
    ¿welcome?, ¿vídeo?) y enlaces directos a su landing, página de vídeo y
    StepForm. Herramienta interna para ver de un vistazo qué tiene implementado
    cada funnel. Disponible en /funnels/ (y vía el proxy en /preview/funnels/).
    """

    def get(self, request):
        base = _base_path(request)
        filas = []
        for f in FunnelForm.objects.all().order_by('escuela', 'region'):
            cfg = f.config or {}
            tiene_video = bool(cfg.get('video')) or f.escuela in _VIDEO_DEFAULTS
            filas.append({
                'escuela': f.escuela,
                'region': f.region,
                'nombre': f.nombre,
                'activo': f.activo,
                'has_landing': 'landing' in cfg,
                'has_welcome': 'welcome' in cfg,
                'has_video': tiene_video,
                'landing_url': f'{base}/{f.escuela}/clase-online-gratuita-{f.region}/',
                'video_url': f'{base}/{f.escuela}/video-clase-{f.region}/',
                'stepform_url': stepform_url(f.escuela, f.region, base=base) or '',
            })
        return render(request, 'pages/public/funnel/status.html', {
            'filas': filas,
            'app_base_path': base,
        })
