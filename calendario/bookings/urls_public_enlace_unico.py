from django.urls import path
from . import views_public as v

app_name = 'public_enlace_unico'
urlpatterns = [
    path('', v.EnlaceUnicoPageView.as_view(), name='booking_page'),
    path('reservar/', v.EnlaceUnicoFormView.as_view(), name='booking_submit'),
    path('slots.json', v.EnlaceUnicoSlotsView.as_view(), name='slots_mes_json'),
]
