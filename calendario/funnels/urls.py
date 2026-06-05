from django.urls import path

from calendario.leads.views import register_lead
from .views import ConfigView, FunnelPageView, ReservarView, ResolverView

app_name = 'funnels'

urlpatterns = [
    path('api/lead/', register_lead, name='register_lead'),
    path('api/<slug:slug>/config/', ConfigView.as_view(), name='config'),
    path('api/<slug:slug>/resolver/', ResolverView.as_view(), name='resolver'),
    path('api/<slug:slug>/reservar/', ReservarView.as_view(), name='reservar'),
    path('<slug:slug>/', FunnelPageView.as_view(), name='funnel_page'),
]
