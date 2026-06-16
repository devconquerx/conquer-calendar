from django.urls import path
from . import views

app_name = 'panel_event_types'
urlpatterns = [
    path('', views.EventTypeListView.as_view(), name='event_type_list'),
    path('nuevo/', views.EventTypeCreateView.as_view(), name='event_type_create'),
    path('<int:pk>/editar/', views.EventTypeUpdateView.as_view(), name='event_type_update'),
    path('<int:pk>/toggle/', views.EventTypeToggleActivoView.as_view(), name='event_type_toggle_activo'),
    path('<int:pk>/eliminar/', views.EventTypeDeleteView.as_view(), name='event_type_delete'),
    path('<int:pk>/enlace-unico/', views.generar_enlace_unico, name='generar_enlace_unico'),
]
