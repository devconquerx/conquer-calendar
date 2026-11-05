from django.urls import path

from . import views_public as v

app_name = 'sms'
urlpatterns = [
    path('<str:codigo>', v.EnlaceCortoSMSView.as_view(), {'destino': 'reagendar_publica'}, name='reagendar'),
    path('<str:codigo>/c', v.EnlaceCortoSMSView.as_view(), {'destino': 'cancelar_publica'}, name='cancelar'),
]
