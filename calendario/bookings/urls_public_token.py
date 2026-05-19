from django.urls import path
from . import views_public as v

app_name = 'public_token'
urlpatterns = [
    path('<uuid:token>/', v.ConfirmacionView.as_view(), name='confirmacion'),
    path('<uuid:token>/cancelar/', v.CancelarPublicaView.as_view(), name='cancelar_publica'),
    path('<uuid:token>/reagendar/', v.ReagendarPublicaView.as_view(), name='reagendar_publica'),
]
