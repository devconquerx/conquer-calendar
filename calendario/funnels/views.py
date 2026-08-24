import json
import logging
import uuid
from datetime import datetime, timezone as dt_timezone

import requests

from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from calendario.bookings.exceptions import ReservaDuplicadaError, SlotNoDisponibleError
from calendario.bookings.models import Reserva
from calendario.bookings.services import crear_reserva, mismo_invitado, reemplazar_reserva
from calendario.bookings.views_public import _enviar_correos_confirmacion
from .ab_tests import tests_para_panel
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


# Campos de tracking que la Prellamada guarda como columnas (snapshot desde el
# JSON `tracking`). journey_id va aparte (es la clave de upsert).
PRELLAMADA_TRACKING_FIELDS = (
    'event_id', 'utm_source', 'utm_campaign', 'utm_medium', 'utm_term',
    'utm_content', 'utm_idcampaign', 'utm_adsetid', 'utm_adid', 'utm_form_variant',
)


def _upsert_prellamada(funnel, journey_id, prellamada_uuid, **fields):
    """Crea o actualiza la Prellamada por su `uuid` de cliente (guardado en
    `token`), igual que conquerx-funnels-new: el front genera `uuidv4()` por
    montaje del formulario (cambia en cada recarga del navegador), así que todas
    las llamadas de un mismo montaje (las intermedias por pregunta + la final)
    comparten el uuid y convergen a la misma fila, y una recarga genera un uuid
    nuevo → fila nueva. Sin uuid válido caemos al `journey_id` (compatibilidad) y,
    sin ninguno, se crea una fila nueva."""
    # Snapshot del tracking a columnas (además del JSON `tracking`).
    tr = fields.get('tracking') if isinstance(fields.get('tracking'), dict) else {}
    cols = {f: (tr.get(f) or '') for f in PRELLAMADA_TRACKING_FIELDS}
    defaults = {'funnel': funnel, 'journey_id': journey_id, **fields, **cols}

    token = None
    if prellamada_uuid:
        try:
            token = uuid.UUID(prellamada_uuid)
        except (ValueError, AttributeError, TypeError):
            token = None

    if token is not None:
        prellamada, _ = Prellamada.objects.update_or_create(
            token=token,
            defaults=defaults,
        )
        return prellamada
    if journey_id:
        prellamada, _ = Prellamada.objects.update_or_create(
            journey_id=journey_id,
            defaults=defaults,
        )
        return prellamada
    return Prellamada.objects.create(**defaults)


@method_decorator(csrf_exempt, name='dispatch')
class ResolverView(View):
    """POST /f/api/<slug>/resolver/ → crea/actualiza la Prellamada.

    Réplica del `submitForm` de conquerx-funnels-new, que envía un request por
    cada pregunta contestada tras el teléfono:

    - `final=False` (intermedio, pre-schedule): upsert del lead+respuestas por
      journey_id, SIN resolver el outcome (en CL EU el teléfono va antes de las
      preguntas de scoring, así que puntuar aquí daría un rechazo falso). Queda
      como `pendiente`.
    - `final=True` (por defecto, submit final): resuelve el outcome, finaliza la
      Prellamada y devuelve el destino (calendario/rechazo).
    """

    def post(self, request, slug):
        funnel = get_object_or_404(FunnelForm, slug=slug, activo=True)
        body = _json_body(request)
        respuestas = body.get('respuestas') or {}
        tracking = body.get('tracking') or {}
        final = body.get('final', True)

        nombre = respuestas.get('name', '') or respuestas.get('nombre', '')
        email = respuestas.get('email', '')
        telefono = respuestas.get('phone', '') or respuestas.get('telefono', '')
        journey_id = (tracking.get('journey_id') or '').strip()
        # uuid de cliente: clave de upsert (token). Se genera por montaje del
        # formulario (cambia en cada recarga), igual que conquerx-funnels-new.
        prellamada_uuid = (tracking.get('uuid') or '').strip()

        # Pre-schedule intermedio: solo captura/actualiza el lead. No puntúa ni
        # resuelve evento (lo hará la llamada final).
        if not final:
            prellamada = _upsert_prellamada(
                funnel, journey_id, prellamada_uuid,
                nombre=nombre, email=email, telefono=telefono,
                respuestas=respuestas, tracking=tracking,
                resultado=Prellamada.Resultado.PENDIENTE,
                score=None, event_type=None,
            )
            return JsonResponse({'ok': True, 'prellamada_token': str(prellamada.token)})

        utm_campaign = (tracking.get('utm_campaign') or '').strip()
        outcome = resolver_outcome(funnel, respuestas, utm_campaign=utm_campaign)

        # En modo Calendly el rango no resuelve EventType local (queda None); la
        # Prellamada se guarda igual (el evento se agenda en Calendly).
        event_type = None
        if outcome['resultado'] == 'calendario' and outcome.get('event_type_slug'):
            from calendario.event_types.models import EventType
            event_type = EventType.objects.filter(
                slug=outcome['event_type_slug'], activo=True
            ).first()

        prellamada = _upsert_prellamada(
            funnel, journey_id, prellamada_uuid,
            nombre=nombre, email=email, telefono=telefono,
            respuestas=respuestas,
            score=outcome['promedio'] if outcome['promedio'] else None,
            resultado=outcome['resultado'],
            tracking=tracking,
            event_type=event_type,
        )

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
                'confirmacion_tipo': event_type.confirmacion_tipo,
                'confirmacion_url': event_type.confirmacion_url or '',
                'mostrar_caja_comentarios': event_type.mostrar_caja_comentarios,
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

        # El event_id de la RESERVA es el del evento Schedule (el que el píxel
        # usa como eventID vía cqx_schedule_event_id), no el del journey: así
        # el CAPI backend y el CRM deduplican contra el píxel, igual que el
        # flujo viejo (Make lo extraía del utm_term de Calendly). La Prellamada
        # conserva el event_id del journey (paridad con el PreSchedule viejo).
        schedule_event_id = (body.get('schedule_event_id') or '').strip()
        tracking_reserva = dict(prellamada.tracking or {})
        if schedule_event_id:
            tracking_reserva['event_id'] = schedule_event_id

        # Reemplazo del duplicado: el front lo manda cuando el visitante acepta
        # en el modal "ya tienes una reserva". Es el confirmacion_token de la
        # reserva vieja, que solo conoce porque se lo devolvimos en el 409 de más
        # abajo. Aun así se valida que sea del mismo evento y del mismo invitado,
        # para que un token suelto no pueda cancelar la reserva de otro.
        reemplazar_token = (body.get('reemplazar_token') or '').strip()
        vieja = None
        if reemplazar_token:
            vieja = Reserva.objects.filter(
                confirmacion_token=reemplazar_token,
                event_type=event_type,
                estado=Reserva.Estado.CONFIRMADA,
                fin_utc__gt=django_timezone.now(),
            ).first()
            # El duplicado puede haberse detectado por teléfono con otro email,
            # así que vale cualquiera de los dos datos — pero uno tiene que
            # coincidir, para que un token suelto no cancele la reserva de otro.
            if vieja is not None and not mismo_invitado(vieja, email, telefono):
                vieja = None
            if vieja is None:
                return JsonResponse(
                    {'ok': False, 'error': 'reemplazo_invalido',
                     'mensaje': 'No encontramos esa reserva. Recarga la página e inténtalo de nuevo.'},
                    status=404,
                )

        try:
            with transaction.atomic():
                if vieja is not None:
                    reserva = reemplazar_reserva(
                        reserva_vieja_pk=vieja.pk,
                        event_type=event_type,
                        inicio_utc=inicio_utc,
                        nombre_invitado=nombre,
                        email_invitado=email,
                        telefono_invitado=telefono,
                        notas=notas,
                        timezone_invitado=tz,
                        tracking=tracking_reserva,
                    )
                else:
                    reserva = crear_reserva(
                        event_type=event_type,
                        inicio_utc=inicio_utc,
                        nombre_invitado=nombre,
                        email_invitado=email,
                        telefono_invitado=telefono,
                        notas=notas,
                        timezone_invitado=tz,
                        tracking=tracking_reserva,
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
                    'host': existing.host.nombre_display(),
                    'event_type_nombre': existing.event_type.nombre,
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
    # Especialización no es una escuela aparte, es una variante de Conquer Blocks
    # (para el CRM y las tags va como 'cb', ver SCHOOL_SLUG_TO_CODE). Necesita su
    # propio producto igualmente, porque su FunnelForm es otro y sin esta entrada
    # /agenda/especializacion/<region>/ da 404. Misma situación que 'kids' con
    # Languages. La URL replica la del funnel viejo (especializacion/<region>).
    'especializacion': 'conquer-blocks-esp',
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
    if escuela == 'conquer-languages' and region == 'ge':
        return f'{base}/ge/schedule'
    if escuela == 'conquer-legal' and region:
        return f'{base}/hub/agendar-{region}'
    producto = PRODUCTO_POR_ESCUELA.get(escuela)
    if producto and region:
        return f'{base}/agenda/{producto}/{region}/'
    return ''


class FunnelAgendaView(View):
    """GET /agenda/<producto>/<región>/ → resuelve el funnel por escuela+región.

    URL pública por marca (ej. /agenda/fullstack/eu/). La API sigue siendo por
    slug (/f/api/<slug>/...): la plantilla recibe el slug del funnel resuelto.

    Puede haber más de un FunnelForm activo para la misma escuela+región (p.ej.
    `blocks-eu` y `blocks-eu-2`, dos landings distintas que comparten el mismo
    quiz/scoring) — se toma el de menor pk (el original) de forma determinista
    en vez de `get_object_or_404`, que lanzaría `MultipleObjectsReturned` (500)
    si hay más de uno. El StepForm de la landing "-2" en sí no pasa por aquí:
    usa la config ya embebida en su propia página (slug explícito), así que
    este fallback solo importa si el visitante llega directo a esta URL.
    """

    def get(self, request, producto, region):
        escuela = PRODUCTO_A_ESCUELA.get(producto)
        funnel = FunnelForm.objects.filter(
            escuela=escuela, region=region, activo=True
        ).order_by('pk').first()
        if funnel is None:
            raise Http404('No hay ningún funnel activo para esta escuela/región.')
        return _spa_render(request, funnel, 'stepform')


def _escuela_por_host(request):
    """Resuelve la escuela según el dominio (Host) usando settings.FUNNEL_HOST_ESCUELA.

    Si el dominio no está en el mapeo (p.ej. calendar.conquerx.com, el
    dominio canónico sin marca propia — o localhost en dev), cae a
    ?escuela=conquer-languages. En los dominios de marca esto nunca se
    alcanza: el Host ya resuelve la escuela, así que no hace falta limitarlo
    a DEBUG.
    """
    host = request.get_host().split(':')[0].lower().strip()
    mapping = getattr(settings, 'FUNNEL_HOST_ESCUELA', {}) or {}
    escuela = mapping.get(host)
    if not escuela and host.startswith('www.'):
        escuela = mapping.get(host[4:])
    if not escuela:
        escuela = request.GET.get('escuela')
    return escuela


# Escuelas que llevan la escuela en el PATH (p.ej. /conquer-blocks/...). El resto
# comparte la ruta raíz y se resuelve por dominio (Host).
_ESCUELAS_RUTA_PATH = ('conquer-blocks', 'conquer-legal')


# Líneas que SOLO tienen StepForm: no publican landing, vídeo ni confirmación
# propios (así es también en el funnel viejo). Son variantes de una marca madre
# —Especialización cuelga de Blocks y Kids de Languages— y su tráfico entra
# directo al formulario desde la web de la marca. Sus URLs de landing/vídeo se
# calcularían igual por convención, pero apuntan a páginas que no existen: el
# panel /funnels/ las marca en gris en lugar de ofrecer enlaces rotos.
_ESCUELAS_SOLO_STEPFORM = ('conquer-blocks-esp', 'conquer-languages-kids')


# URLs de la página de video por marca. Conquer Legal replica las rutas de
# producción bajo /hub/ (conquerlegal.com/hub/video-<region>). Conquer Finance
# replica EXACTAMENTE las URLs vivas de www.conquerfinance.com (Webflow): sin
# barra final, y la confirmación compartida entre regiones sin sufijo — cuando
# el dominio pase a servirse desde aquí no puede cambiar ni un carácter.
def _video_url(escuela, region, base='', slug=None):
    # Segunda landing de Blocks EU (blocks-eu-2, réplica de cb-eu-2): tiene su
    # propia URL de video (VSL corta), distinta de la de blocks-eu aunque
    # comparten escuela+región — de ahí el caso especial por slug.
    if slug == 'blocks-eu-2':
        return f'{base}/conquer-blocks/video-2-clase-eu/'
    # Conquer Languages GE (la variante en inglés) no sigue la convención de
    # region: replica las rutas de producción /ge/*, que están en inglés.
    if escuela == 'conquer-languages' and region == 'ge':
        return f'{base}/ge/video-training'
    if escuela == 'conquer-legal':
        return f'{base}/hub/video-{region}'
    if escuela == 'conquer-finance':
        return f'{base}/video-clase-{region}'
    if escuela in _ESCUELAS_RUTA_PATH:
        return f'{base}/{escuela}/video-clase-{region}/'
    return f'{base}/video-clase-{region}/'


# URL de la landing de registro de lead por marca (misma convención).
def _landing_url(escuela, region, base='', slug=None):
    if slug == 'blocks-eu-2':
        return f'{base}/conquer-blocks/clase-2-online-gratuita-eu/'
    if escuela == 'conquer-languages' and region == 'ge':
        return f'{base}/ge/free-online-training'
    if escuela == 'conquer-legal':
        return f'{base}/hub/registro-{region}'
    if escuela == 'conquer-finance':
        return f'{base}/clase-online-gratuita-{region}'
    if escuela in _ESCUELAS_RUTA_PATH:
        return f'{base}/{escuela}/clase-online-gratuita-{region}/'
    return f'{base}/clase-online-gratuita-{region}/'


# URL de la página de confirmación de llamada por marca (misma convención).
def confirmacion_url(escuela, region, base=''):
    if escuela == 'conquer-languages' and region == 'ge':
        return f'{base}/ge/confirmation'
    if escuela == 'conquer-legal':
        return f'{base}/hub/confirmacion'
    if escuela == 'conquer-finance':
        # Página única para todas las regiones, como en producción
        # (www.conquerfinance.com/confirmacion-llamada).
        return f'{base}/confirmacion-llamada'
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
    # VSL propia de Conquer Legal, optimizada a H.264 High 1080p (8-bit, AAC,
    # faststart) y servida como MP4 directo desde el mismo pull zone público que
    # el resto de escuelas (vslconquerx.b-cdn.net), que el reproductor VSL carga
    # en un <video> nativo.
    'conquer-legal': {
        'videoUrls': [
            'https://vslconquerx.b-cdn.net/Conquerlegal/Conquer%20Legal%20VSL%20-%20V1%20-%20WEB-1080p-h264.mp4',
        ],
        'buttonPercent': 75,
    },
    'conquer-languages': {
        'videoUrls': [
            'https://vslconquerx.b-cdn.net/conquerlanguages/vsl-cl-original-v1-compress.mp4',
        ],
        'buttonPercent': 75,
    },
}


# Plantillas de landing por marca (las que no estén aquí usan la landing React).
# Vacío: Languages tenía aquí una plantilla suelta (landing_languages.html) que
# se quedó fuera del sistema de diseño paperboard y, sobre todo, fuera del SPA:
# su formulario mandaba al backend solo nombre y email, sin UTMs, click IDs ni
# cookies de píxel, y navegaba al vídeo con recarga completa. Ahora Languages
# usa el renderer compartido, igual que Blocks, Finance y Legal.
_LANDING_TEMPLATE_POR_ESCUELA = {}


# Plantillas de la página de vídeo por marca (las que no estén aquí usan la
# página de vídeo React por defecto, dentro del shell SPA). Vacío por el mismo
# motivo que el mapa de arriba.
_VIDEO_TEMPLATE_POR_ESCUELA = {}


def _render_ssr(*, stage, slug, escuela, region, program,
                form_config, video_enabled, urls, search):
    """Pide al servicio Node SSR el HTML inicial de #funnel-root para esta etapa.

    Devuelve '' (→ CSR en el cliente, el comportamiento de hoy) si el SSR está
    deshabilitado, si la combinación escuela:stage no está en el allowlist, o si
    el servicio falla o tarda más del timeout. Nunca propaga errores ni añade
    latencia perceptible: el fallback a CSR es seguro.
    """
    if not getattr(settings, 'FUNNEL_SSR_ENABLED', False):
        return ''
    allowlist = getattr(settings, 'FUNNEL_SSR_ALLOWLIST', set())
    # '*' en el allowlist = todas las combinaciones (rollout completo).
    if '*' not in allowlist and f'{escuela}:{stage}' not in allowlist:
        return ''
    payload = {
        'stage': stage,
        'slug': slug,
        'escuela': escuela,
        'region': region,
        'program': program,
        'formConfig': form_config,
        'videoEnabled': video_enabled,
        'urls': urls,
        'search': search,
    }
    try:
        resp = requests.post(
            settings.FUNNEL_SSR_URL,
            json=payload,
            timeout=(0.3, getattr(settings, 'FUNNEL_SSR_TIMEOUT', 0.4)),
        )
        resp.raise_for_status()
        return resp.json().get('html', '') or ''
    except (requests.RequestException, ValueError) as exc:
        logger.warning('SSR fallback a CSR (%s:%s): %s', escuela, stage, exc)
        return ''


def _spa_render(request, funnel, stage, escuela=None, region=None):
    """Renderiza el shell único de la SPA del funnel en la etapa indicada.

    Todas las etapas (landing → video → stepform → confirmación) comparten
    plantilla y bundle (src/funnel-spa.jsx): la SPA pinta la pantalla según
    `stage` y navega entre etapas con pushState usando las URLs canónicas que
    se pasan aquí. `funnel` puede ser None (confirmación sin funnel activo).
    """
    from .context_processors import get_gtm_config, get_pixel_ids
    escuela = escuela or (funnel.escuela if funnel else '')
    region = region or (funnel.region if funnel else '')
    base = _base_path(request)
    cfg = dict((funnel.config if funnel else None) or {})
    if not cfg.get('video') and escuela in _VIDEO_DEFAULTS:
        cfg['video'] = _VIDEO_DEFAULTS[escuela]

    slug = funnel.slug if funnel else ''
    program = PRODUCTO_POR_ESCUELA.get(escuela, '')
    video_enabled = bool(cfg.get('video'))
    landing_url = _landing_url(escuela, region, base=base, slug=slug) if region else ''
    video_url = _video_url(escuela, region, base=base, slug=slug) if region else ''
    stepform_u = stepform_url(escuela, region, base=base)
    confirmation_url = confirmacion_url(escuela, region, base=base) if region else ''

    # HTML del SSR para #funnel-root (vacío → CSR). El query string se pasa con
    # el '?' inicial para que coincida exactamente con window.location.search del
    # cliente y el prefill server == cliente (sin hydration mismatch).
    qs = request.META.get('QUERY_STRING', '')
    ssr_html = _render_ssr(
        stage=stage,
        slug=slug,
        escuela=escuela,
        region=region,
        program=program,
        form_config=cfg,
        video_enabled=video_enabled,
        urls={
            'landing': landing_url,
            'video': video_url,
            'stepform': stepform_u,
            'confirmation': confirmation_url,
        },
        search=('?' + qs) if qs else '',
    )

    respuesta = render(
        request,
        'pages/public/funnel/spa.html',
        {
            'funnel': funnel,
            'slug': slug,
            'escuela': escuela,
            'region': region,
            'program': program,
            'stage': stage,
            'funnel_config': cfg,
            'video_enabled': video_enabled,
            'landing_url': landing_url,
            'video_url': video_url,
            'stepform_url': stepform_u,
            'confirmation_url': confirmation_url,
            'pixel_ids': get_pixel_ids(escuela),
            'gtm': get_gtm_config(escuela),
            'app_base_path': base,
            'ssr_html': ssr_html,
        },
    )

    # El HTML del funnel NO se cachea en ningún sitio. Sin `Cache-Control` las
    # cachés intermedias aplican heurísticas propias y se quedan con una copia:
    # así fue como, tras mover conquerlanguages.com a Django, el navegador
    # embebido de TikTok siguió sirviendo durante horas la landing del proyecto
    # viejo a parte de los visitantes —misma URL, mismo anuncio, unos con la
    # nueva y otros con la vieja—, y esos leads se iban a Make en vez de al
    # calendario. Además cada respuesta lleva dentro `funnel-config` (contenido
    # y A/B del visitante), que tampoco debe compartirse entre usuarios.
    respuesta['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    respuesta['Pragma'] = 'no-cache'
    return respuesta


class FunnelClaseView(View):
    """GET de las landings de registro de lead:

      - /conquer-blocks/clase-online-gratuita-<region>/  → escuela fija en el path
      - /clase-online-gratuita-<region>/                 → escuela resuelta por Host
        (conquerlanguages.* → conquer-languages, conquerfinance.* → conquer-finance)

    `slug` (opcional, vía kwarg de urls.py) resuelve un FunnelForm concreto en
    vez de por escuela+región — necesario para landings "extra" que comparten
    escuela+región con otra (p.ej. blocks-eu-2, réplica de la segunda landing
    EU de Conquer Blocks del funnel viejo, cb-eu-2).
    """

    def get(self, request, region, escuela=None, slug=None):
        if escuela is None:
            escuela = _escuela_por_host(request)
        if not escuela:
            raise Http404('No se pudo resolver la escuela para este dominio.')
        if slug:
            funnel = get_object_or_404(FunnelForm, slug=slug, activo=True)
        else:
            # Puede haber más de un FunnelForm activo por escuela+región (ver
            # blocks-eu-2 arriba): se toma el de menor pk de forma determinista
            # en vez de get_object_or_404, que lanzaría MultipleObjectsReturned.
            funnel = FunnelForm.objects.filter(
                escuela=escuela, region=region, activo=True
            ).order_by('pk').first()
            if funnel is None:
                raise Http404('No hay ningún funnel activo para esta escuela/región.')
        # Marcas con plantilla propia (HTML + Tailwind, p.ej. languages) siguen
        # el flujo multipágina; el resto entra al shell SPA en la etapa landing.
        template_name = _LANDING_TEMPLATE_POR_ESCUELA.get(funnel.escuela)
        if template_name is None:
            return _spa_render(request, funnel, 'landing')
        from .context_processors import get_gtm_config, get_pixel_ids
        # Siguiente etapa tras la landing: la página de video si la marca la tiene
        # configurada; si no, directo al StepForm (/agenda/<producto>/<region>/).
        cfg = funnel.config or {}
        if cfg.get('video') or funnel.escuela in _VIDEO_DEFAULTS:
            next_url = _video_url(funnel.escuela, funnel.region, base=_base_path(request))
        else:
            next_url = stepform_url(funnel.escuela, funnel.region, base=_base_path(request))
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
                'gtm': get_gtm_config(funnel.escuela),
                'app_base_path': _base_path(request),
            },
        )


class FunnelVideoView(View):
    """GET de la página de video (VSL), entre la landing y el StepForm:

      - /conquer-blocks/video-clase-<region>/  → escuela fija en el path
      - /video-clase-<region>/                 → escuela resuelta por Host

    `slug` (opcional, vía kwarg de urls.py) resuelve un FunnelForm concreto en
    vez de por escuela+región — ver FunnelClaseView (blocks-eu-2).
    """

    def get(self, request, region, escuela=None, slug=None):
        if escuela is None:
            escuela = _escuela_por_host(request)
        if not escuela:
            raise Http404('No se pudo resolver la escuela para este dominio.')
        if slug:
            funnel = get_object_or_404(FunnelForm, slug=slug, activo=True)
        else:
            funnel = FunnelForm.objects.filter(
                escuela=escuela, region=region, activo=True
            ).order_by('pk').first()
            if funnel is None:
                raise Http404('No hay ningún funnel activo para esta escuela/región.')
        # Marcas con plantilla propia (HTML + Tailwind + Plyr, p.ej. languages)
        # siguen el flujo multipágina; el resto entra al shell SPA en la etapa
        # de vídeo.
        template_name = _VIDEO_TEMPLATE_POR_ESCUELA.get(funnel.escuela)
        if template_name is None:
            return _spa_render(request, funnel, 'video')
        from .context_processors import get_gtm_config, get_pixel_ids
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
            template_name,
            {
                'funnel': funnel,
                'slug': funnel.slug,
                'next_url': next_url,
                'video_config': video_cfg,
                'pixel_ids': get_pixel_ids(funnel.escuela),
                'gtm': get_gtm_config(funnel.escuela),
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
        return _spa_render(request, funnel, 'confirmation', escuela=escuela, region=region)


class FunnelStatusView(View):
    """Panel de estado de los funnels.

    Lista cada escuela×región registrada con su estado (activo, ¿tiene landing?,
    ¿welcome?, ¿vídeo?) y enlaces directos a su landing, página de vídeo y
    StepForm. Herramienta interna para ver de un vistazo qué tiene implementado
    cada funnel. Disponible en /funnels/ (y vía el proxy en /preview/funnels/).
    """

    def get(self, request):
        base = _base_path(request)
        publicos = getattr(settings, 'FUNNEL_PUBLIC_BASE', None) or {}
        filas = []
        for f in FunnelForm.objects.all().order_by('escuela', 'region'):
            cfg = f.config or {}
            tiene_video = bool(cfg.get('video')) or f.escuela in _VIDEO_DEFAULTS

            # Base pública de la marca (FUNNEL_PUBLIC_BASE), si la tiene: los
            # enlaces salen absolutos contra su dominio en vez de contra el del
            # panel, que es donde el funnel se ve de verdad. Ese valor ya trae su
            # propio prefijo cuando toca (p.ej. .../preview mientras dura el
            # corte), así que SUSTITUYE a app_base_path — sumarlos lo duplicaría.
            publico = (publicos.get(f.escuela) or '').rstrip('/')
            ruta_base = '' if publico else base

            def _abs(url):
                return f'{publico}{url}' if (publico and url) else url

            # Las escuelas SIN la escuela en el path (finance, languages…)
            # resuelven por Host, así que sus rutas raíz no funcionan desde el
            # dominio del panel (calendar.localhost / el dominio del calendario).
            # Se les añade ?escuela=<slug>: en dev DEBUG lo usa el fallback de
            # _escuela_por_host; en los dominios de marca el parámetro se ignora.
            # Con base pública sobra: ahí el Host ya resuelve la escuela.
            def _link(url):
                if not url or publico or f.escuela in _ESCUELAS_RUTA_PATH:
                    return _abs(url)
                return f'{url}?escuela={f.escuela}'

            # Etapas que esta línea publica de verdad. Las de solo-StepForm no
            # tienen landing/vídeo/confirmación propios, así que se dejan vacías
            # en lugar de calcular una URL que daría 404.
            solo_stepform = f.escuela in _ESCUELAS_SOLO_STEPFORM
            landing = '' if solo_stepform else _link(_landing_url(f.escuela, f.region, base=ruta_base, slug=f.slug))
            video = '' if solo_stepform else _link(_video_url(f.escuela, f.region, base=ruta_base, slug=f.slug))
            confirmacion = '' if solo_stepform else _link(confirmacion_url(f.escuela, f.region, base=ruta_base))

            filas.append({
                'escuela': f.escuela,
                'region': f.region,
                'nombre': f.nombre,
                'slug': f.slug,
                'activo': f.activo,
                'solo_stepform': solo_stepform,
                'has_landing': 'landing' in cfg,
                'has_welcome': 'welcome' in cfg,
                'has_video': tiene_video,
                'landing_url': landing,
                'video_url': video,
                'stepform_url': _abs(stepform_url(f.escuela, f.region, base=ruta_base)) or '',
                'confirmation_url': confirmacion,
            })
        # Pantallas de evento: no son funnels (no tienen StepForm ni reserva), así
        # que no salen de FunnelForm, pero se listan aquí para tenerlas a mano.
        # El enlace se arma aparte del bucle de arriba: aquel resuelve el dominio
        # público por funnel, y aquí hay que hacerlo por escuela del evento.
        from .evento_views import EVENTOS
        eventos = []
        for escuela, datos in sorted(EVENTOS.items()):
            publico_ev = (publicos.get(escuela) or '').rstrip('/')
            # Cada marca sirve su evento en una ruta distinta (Blocks en
            # /evento/evento-online, Languages en /cl-evento), tal como estaban
            # en Webflow.
            ruta = datos.get('ruta', 'evento/evento-online')
            if publico_ev:
                url = f'{publico_ev}/{ruta}'
            else:
                # En local/dev la escuela no se resuelve por dominio: va en la query.
                url = f'{base}/{ruta}?escuela={escuela}'
            eventos.append({
                'escuela': escuela,
                'titulo': datos['titulo_pagina'],
                'barra': datos['barra'],
                'url': url,
            })

        return render(request, 'pages/public/funnel/status.html', {
            'filas': filas,
            'eventos': eventos,
            'app_base_path': base,
            'tests_ab': tests_para_panel(),
        })
