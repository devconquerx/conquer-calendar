from django.urls import path
from . import views_public as v

app_name = 'public_booking'
urlpatterns = [
    path('', v.BookingPageView.as_view(), name='booking_page'),
    path('reservar/', v.BookingFormView.as_view(), name='booking_submit'),
    path('slots.json', v.SlotsMesJSONView.as_view(), name='slots_mes_json'),
]
