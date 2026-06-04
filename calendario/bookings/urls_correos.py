from django.urls import path
from .views_correos import PlantillaCorreoPreviewView

app_name = 'panel_correos'
urlpatterns = [
    path('plantillas/<int:pk>/preview/', PlantillaCorreoPreviewView.as_view(), name='plantilla_preview'),
]
