import os

from django.conf import settings
from django.contrib import admin
from django.urls import re_path
from django.urls import path, include
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import JsonResponse
from django.views.generic import RedirectView

from calendario.users.views import MagicLoginView, MagicLoginStopView
from calendario.funnels.evento_views import EventoView, GraciasView, PaginaDeCampanaView
from calendario.funnels.views import (
    FunnelAgendaView, FunnelClaseView, FunnelConfirmationView,
    FunnelVideoView, FunnelStatusView,
)


def health(request):
    """Latido del servicio + de qué despliegue viene la respuesta.

    `sha` (sellado en la imagen al construirla) y `color` (blue/green) los usa
    deploy/prod-deploy.sh para comprobar que la URL pública sirve exactamente el
    commit que se acaba de desplegar. En local salen vacíos.
    """
    return JsonResponse({
        "status": "ok",
        "service": "conquer-calendario",
        "sha": os.environ.get("DEPLOY_SHA", ""),
        "color": os.environ.get("DEPLOY_COLOR", ""),
    })


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('acceder-como/stop/', MagicLoginStopView.as_view(), name='magic_login_stop'),
    path('acceder-como/<str:token>/', MagicLoginView.as_view(), name='magic_login'),
    path('health/', health, name='health'),
    path('panel/', include('calendario.users.urls')),
    path('panel/', include('calendario.permisos.urls')),
    path('panel/event-types/', include('calendario.event_types.urls')),
    path('panel/disponibilidad/', include('calendario.availability.urls')),
    path('panel/reservas/', include('calendario.bookings.urls_panel')),
    path('panel/correos/', include('calendario.bookings.urls_correos')),
    path('panel/grupos/', include('calendario.grupos.urls')),
    path('', RedirectView.as_view(url='/panel/', permanent=False)),
    path('r/', include('calendario.bookings.urls_public_token')),
    path('u/<uuid:token>/', include('calendario.bookings.urls_public_enlace_unico')),
    path('e/<slug:slug_equipo>/', include('calendario.bookings.urls_public_team')),
    path('f/', include('calendario.funnels.urls')),
    # Pantalla del evento en directo (lanzamiento). Es informativa: presenta el
    # directo y registra en un popup, sin StepForm ni reserva detrás, así que no
    # cuelga de un FunnelForm. La escuela se resuelve por dominio; en local, con
    # ?escuela=conquer-blocks. Réplica de la página que servía Webflow.
    re_path(r'^evento/evento-online/?$', EventoView.as_view(), name='evento_online'),
    # Languages sirve la suya en otra ruta (así está en su Webflow), así que se
    # registra aparte y lleva la escuela fijada: su dominio no es ambiguo.
    re_path(r'^cl-evento/?$', EventoView.as_view(), {'escuela': 'conquer-languages'},
            name='evento_languages'),
    # Página de "gracias" del evento: presenta el grupo de WhatsApp y salta a él
    # sola a los 15 s. Blocks y Finance la sirven bajo /evento/; Languages en la
    # raíz, con otro nombre, tal como en Webflow.
    re_path(r'^evento/gracias-comunidad/?$', GraciasView.as_view(), name='evento_gracias'),
    re_path(r'^grupos-comunidad/?$', GraciasView.as_view(), {'escuela': 'conquer-languages'},
            name='evento_gracias_languages'),
    # Páginas de evento de campaña (Coding Week…): una ruta por campaña, bajo
    # /evento/, tal como las servía Webflow.
    re_path(r'^evento/(?P<pagina>evento-coding-week-eu|evento-testimonios)/?$', PaginaDeCampanaView.as_view(),
            name='evento_campana'),
    # Languages sirve la suya bajo /eventos/ (en plural), como en su Webflow.
    re_path(r'^eventos/(?P<pagina>bitacora)/?$', PaginaDeCampanaView.as_view(),
            name='evento_campana_languages'),
    # Panel interno de estado de los funnels (lista escuelas + enlaces).
    path('funnels/', FunnelStatusView.as_view(), name='funnel_status'),
    # URLs públicas canónicas por marca/producto (antes del catch-all de booking).
    path('agenda/<slug:producto>/<slug:region>/', FunnelAgendaView.as_view(), name='funnel_agenda'),
    # Landings de registro de lead. Cualquier escuela puede servirse por path
    # (/conquer-<marca>/clase-online-gratuita-<region>/); además languages y
    # finance comparten la ruta raíz y se resuelven por dominio (Host).
    re_path(
        r'^(?P<escuela>conquer-[a-z-]+)/clase-online-gratuita-(?P<region>latam|eu|us)/?$',
        FunnelClaseView.as_view(), name='clase_escuela',
    ),
    re_path(
        r'^clase-online-gratuita-(?P<region>latam|eu|us)/?$',
        FunnelClaseView.as_view(), name='clase_host',
    ),
    # Segunda landing EU de Conquer Blocks (blocks-eu-2, réplica exacta de
    # /conquer-blocks/clase-2-online-gratuita-eu del funnel viejo, cb-eu-2):
    # comparte escuela+región con blocks-eu pero es un FunnelForm propio, así
    # que va por slug explícito en vez de por el patrón genérico de arriba.
    re_path(
        r'^conquer-blocks/clase-2-online-gratuita-eu/?$',
        FunnelClaseView.as_view(), {'escuela': 'conquer-blocks', 'region': 'eu', 'slug': 'blocks-eu-2'},
        name='clase_cb_eu_2',
    ),
    # Página de video (VSL), entre la landing y el StepForm. Por path para
    # cualquier escuela; por Host en la ruta raíz.
    re_path(
        r'^(?P<escuela>conquer-[a-z-]+)/video-clase-(?P<region>latam|eu|us)/?$',
        FunnelVideoView.as_view(), name='video_escuela',
    ),
    re_path(
        r'^conquer-blocks/video-2-clase-eu/?$',
        FunnelVideoView.as_view(), {'escuela': 'conquer-blocks', 'region': 'eu', 'slug': 'blocks-eu-2'},
        name='video_cb_eu_2',
    ),
    re_path(
        r'^video-clase-(?P<region>latam|eu|us)/?$',
        FunnelVideoView.as_view(), name='video_host',
    ),
    # Página de confirmación de llamada (tras agendar). La región es opcional para
    # admitir la URL histórica /conquer-blocks/confirmacion-llamada/.
    re_path(
        r'^(?P<escuela>conquer-[a-z-]+)/confirmacion-llamada(?:-(?P<region>latam|eu|us))?/?$',
        FunnelConfirmationView.as_view(), name='confirmacion_escuela',
    ),
    re_path(
        r'^confirmacion-llamada(?:-(?P<region>latam|eu|us))?/?$',
        FunnelConfirmationView.as_view(), name='confirmacion_host',
    ),
    # Rutas /hub/* que replican exactamente las URLs de producción de Conquer
    # Legal (conquerlegal.com/hub/registro-eu, /hub/video-eu, /hub/confirmacion).
    # El prefijo /hub/ es propio de Legal, así que fijamos escuela=conquer-legal.
    # Deben ir antes del catch-all de booking para que "hub/<algo>" no se
    # interprete como user_slug/event_type_slug.
    re_path(
        r'^hub/registro-(?P<region>latam|eu|us)/?$',
        FunnelClaseView.as_view(), {'escuela': 'conquer-legal'},
        name='clase_hub_legal',
    ),
    re_path(
        r'^hub/video-(?P<region>latam|eu|us)/?$',
        FunnelVideoView.as_view(), {'escuela': 'conquer-legal'},
        name='video_hub_legal',
    ),
    re_path(
        r'^hub/agendar-(?P<region>latam|eu|us)/?$',
        FunnelAgendaView.as_view(), {'producto': 'legal'},
        name='agenda_hub_legal',
    ),
    re_path(
        r'^hub/confirmacion/?$',
        FunnelConfirmationView.as_view(), {'escuela': 'conquer-legal'},
        name='confirmacion_hub_legal',
    ),

    # Rutas /ge/* de Conquer Languages GE, la variante en inglés. Replican las
    # de producción (conquerlanguages.com/ge/free-online-training, /ge/video-training,
    # /ge/schedule), que no siguen la convención `<algo>-<region>` del resto:
    # están en inglés y la región va en el prefijo. Por eso se fija la región a
    # 'ge' aquí en vez de capturarla del path. Van antes del catch-all de
    # booking, igual que las de Legal.
    re_path(
        r'^ge/free-online-training/?$',
        FunnelClaseView.as_view(), {'escuela': 'conquer-languages', 'region': 'ge'},
        name='clase_ge_languages',
    ),
    re_path(
        r'^ge/video-training/?$',
        FunnelVideoView.as_view(), {'escuela': 'conquer-languages', 'region': 'ge'},
        name='video_ge_languages',
    ),
    re_path(
        r'^ge/schedule/?$',
        FunnelAgendaView.as_view(), {'producto': 'english', 'region': 'ge'},
        name='agenda_ge_languages',
    ),
    re_path(
        r'^ge/confirmation/?$',
        FunnelConfirmationView.as_view(), {'escuela': 'conquer-languages', 'region': 'ge'},
        name='confirmacion_ge_languages',
    ),
    path('webhooks/', include('calendario.google_calendar.urls')),
    re_path(
        r'^(?P<user_slug>[-a-zA-Z0-9_.]+)/(?P<event_type_slug>[-a-zA-Z0-9_]+)/',
        include('calendario.bookings.urls_public_booking'),
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    # Se sirven por la pila normal de URLs (runserver arranca con --nostatic) para
    # que pasen por los middleware y lleguen con las cabeceras de no-caché.
    urlpatterns += staticfiles_urlpatterns()

admin.site.site_header = "Conquer Calendario"
admin.site.site_title = "Conquer Calendario"
admin.site.index_title = "Conquer Calendario"
