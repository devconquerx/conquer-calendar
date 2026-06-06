from django.urls import path

from calendario.leads.views import register_lead, video_progress
from .views import ConfigView, ReservarView, ResolverView

app_name = 'funnels'

# Solo API bajo /f/api/. La página del StepForm se sirve en la URL canónica
# /agenda/<producto>/<region>/ (FunnelAgendaView en config/urls.py).
urlpatterns = [
    path('api/lead/', register_lead, name='register_lead'),
    path('api/video-progress/', video_progress, name='video_progress'),
    path('api/<slug:slug>/config/', ConfigView.as_view(), name='config'),
    path('api/<slug:slug>/resolver/', ResolverView.as_view(), name='resolver'),
    path('api/<slug:slug>/reservar/', ReservarView.as_view(), name='reservar'),
]
