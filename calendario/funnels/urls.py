from django.urls import path

from calendario.leads.views import register_lead, video_progress
from .consentimiento_views import conquerx_cookies_js
from .views import ConfigView, ReservarView, ResolverView

app_name = 'funnels'

# Solo API bajo /f/api/. La página del StepForm se sirve en la URL canónica
# /agenda/<producto>/<region>/ (FunnelAgendaView en config/urls.py).
urlpatterns = [
    # Banner de consentimiento empaquetado para las páginas que sirve Webflow.
    # Va bajo /f/ porque ese prefijo ya está enrutado a Django en los dominios
    # de marca: así no hay que tocar Cloudflare y sigue llegando el país del
    # visitante (ver consentimiento_views).
    path('conquerx-cookies.js', conquerx_cookies_js, name='conquerx_cookies_js'),
    path('api/lead/', register_lead, name='register_lead'),
    path('api/video-progress/', video_progress, name='video_progress'),
    path('api/<slug:slug>/config/', ConfigView.as_view(), name='config'),
    path('api/<slug:slug>/resolver/', ResolverView.as_view(), name='resolver'),
    path('api/<slug:slug>/reservar/', ReservarView.as_view(), name='reservar'),
]
