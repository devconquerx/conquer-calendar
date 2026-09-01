from django.urls import path

from . import views_panel

app_name = 'panel_contenido'

urlpatterns = [
    path('', views_panel.ListaDePaginasView.as_view(), name='lista'),
    path('<slug:clave>/', views_panel.EditorView.as_view(), name='editor'),
    path('<slug:clave>/guardar/', views_panel.guardar_borrador, name='guardar'),
    path('<slug:clave>/publicar/', views_panel.publicar, name='publicar'),
    path('<slug:clave>/descartar/', views_panel.descartar_borrador, name='descartar'),
]
