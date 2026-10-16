from django.urls import path
from . import views_public as v

app_name = 'public_token'
urlpatterns = [
    path('limite-reservas/', v.LimiteReservasView.as_view(), name='limite_reservas'),
    path('no-procesada/', v.ReservaNoProcesadaView.as_view(), name='reserva_no_procesada'),
    path('<uuid:token>/', v.ConfirmacionView.as_view(), name='confirmacion'),
    path('<uuid:token>/cancelar/', v.CancelarPublicaView.as_view(), name='cancelar_publica'),
    path('<uuid:token>/confirmar/', v.ConfirmarAsistenciaPublicaView.as_view(), name='confirmar_asistencia_publica'),
    path('<uuid:token>/reagendar/', v.ReagendarPublicaView.as_view(), name='reagendar_publica'),
    # Termina en `reservar/` a propósito, como las demás: el JS de la página
    # reconoce así la respuesta del envío y no la redirige a un GET.
    path('<uuid:token>/reagendar/reservar/', v.ReagendarFormView.as_view(), name='reagendar_submit'),
    path('<uuid:token>/reagendar/slots.json', v.ReagendarSlotsView.as_view(), name='reagendar_slots'),
    path('<uuid:token>/reemplazar/', v.ReemplazarPublicaView.as_view(), name='reemplazar_publica'),
]
