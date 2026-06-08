from django.conf import settings
from django.contrib import admin
from django.urls import re_path
from django.urls import path, include
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView

from calendario.users.views import MagicLoginView, MagicLoginStopView
from calendario.funnels.views import (
    FunnelAgendaView, FunnelClaseView, FunnelConfirmationView,
    FunnelVideoView,
)


def health(request):
    return JsonResponse({"status": "ok", "service": "conquer-calendario"})


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
    path('e/<slug:slug_equipo>/', include('calendario.bookings.urls_public_team')),
    path('f/', include('calendario.funnels.urls')),
    # URLs públicas canónicas por marca/producto (antes del catch-all de booking).
    path('agenda/<slug:producto>/<slug:region>/', FunnelAgendaView.as_view(), name='funnel_agenda'),
    # Landings de registro de lead: blocks lleva la escuela en el path; languages
    # y finance comparten la ruta raíz y se resuelven por dominio (Host).
    re_path(
        r'^conquer-blocks/clase-online-gratuita-(?P<region>latam|eu|us)/?$',
        FunnelClaseView.as_view(), {'escuela': 'conquer-blocks'}, name='clase_blocks',
    ),
    re_path(
        r'^clase-online-gratuita-(?P<region>latam|eu|us)/?$',
        FunnelClaseView.as_view(), name='clase_host',
    ),
    # Página de video (VSL), entre la landing y el StepForm. blocks lleva la
    # escuela en el path; el resto se resuelve por dominio (Host).
    re_path(
        r'^conquer-blocks/video-clase-(?P<region>latam|eu|us)/?$',
        FunnelVideoView.as_view(), {'escuela': 'conquer-blocks'}, name='video_blocks',
    ),
    re_path(
        r'^video-clase-(?P<region>latam|eu|us)/?$',
        FunnelVideoView.as_view(), name='video_host',
    ),
    # Página de confirmación de llamada (tras agendar). La región es opcional para
    # admitir la URL histórica /conquer-blocks/confirmacion-llamada/.
    re_path(
        r'^conquer-blocks/confirmacion-llamada(?:-(?P<region>latam|eu|us))?/?$',
        FunnelConfirmationView.as_view(), {'escuela': 'conquer-blocks'}, name='confirmacion_blocks',
    ),
    re_path(
        r'^confirmacion-llamada(?:-(?P<region>latam|eu|us))?/?$',
        FunnelConfirmationView.as_view(), name='confirmacion_host',
    ),
    re_path(
        r'^(?P<user_slug>[-a-zA-Z0-9_.]+)/(?P<event_type_slug>[-a-zA-Z0-9_]+)/',
        include('calendario.bookings.urls_public_booking'),
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Conquer Calendario"
admin.site.site_title = "Conquer Calendario"
admin.site.index_title = "Conquer Calendario"
