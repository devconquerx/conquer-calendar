from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView


def health(request):
    return JsonResponse({"status": "ok", "service": "conquer-calendario"})


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('health/', health, name='health'),
    path('panel/', include('calendario.users.urls')),
    path('panel/', include('calendario.permisos.urls')),
    path('panel/event-types/', include('calendario.event_types.urls')),
    path('panel/disponibilidad/', include('calendario.availability.urls')),
    path('panel/reservas/', include('calendario.bookings.urls_panel')),
    path('', RedirectView.as_view(url='/panel/', permanent=False)),
    path('r/', include('calendario.bookings.urls_public_token')),
    path('e/<slug:slug_equipo>/', include('calendario.bookings.urls_public_team')),
    path('<slug:user_slug>/<slug:event_type_slug>/', include('calendario.bookings.urls_public_booking')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Conquer Calendario"
admin.site.site_title = "Conquer Calendario"
admin.site.index_title = "Conquer Calendario"
