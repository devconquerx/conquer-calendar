from django.urls import path

from . import views

app_name = 'panel_permisos'

urlpatterns = [
    path('roles/', views.RolListView.as_view(), name='rol_list'),
    path('roles/nuevo/', views.RolCreateView.as_view(), name='rol_create'),
    path('roles/<int:pk>/editar/', views.RolUpdateView.as_view(), name='rol_update'),
    path('roles/<int:pk>/eliminar/', views.RolDeleteView.as_view(), name='rol_delete'),
    path('permisos/', views.PermisoListView.as_view(), name='permiso_list'),
]
