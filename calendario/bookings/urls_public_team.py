from django.urls import path
from . import views_public as v

app_name = 'public_team'
urlpatterns = [
    path('', v.TeamBookingPageView.as_view(), name='booking_page'),
    path('reservar/', v.TeamBookingFormView.as_view(), name='booking_submit'),
    path('slots.json', v.SlotsMesJSONTeamView.as_view(), name='slots_mes_json'),
]
