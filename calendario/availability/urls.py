from django.urls import path
from . import views

app_name = 'panel_disponibilidad'
urlpatterns = [
    path('', views.MiDisponibilidadListView.as_view(), name='bloque_list'),
    path('bloques/nuevo/', views.BloqueHorarioCreateView.as_view(), name='bloque_create'),
    path('bloques/<int:pk>/eliminar/', views.BloqueHorarioDeleteView.as_view(), name='bloque_delete'),
    path('bloques/dia/<int:dia>/limpiar/', views.LimpiarDiaView.as_view(), name='dia_limpiar'),
    path('bloques-fecha/nuevo/', views.BloqueHorarioFechaCreateView.as_view(), name='bloque_fecha_create'),
    path('bloques-fecha/<int:pk>/eliminar/', views.BloqueHorarioFechaDeleteView.as_view(), name='bloque_fecha_delete'),
    path('bloques-fecha/<str:fecha>/limpiar/', views.LimpiarFechaView.as_view(), name='fecha_limpiar'),
]
