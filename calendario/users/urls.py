from django.urls import path

from . import views

app_name = 'panel_usuarios'

urlpatterns = [
    path('', views.PanelDashboardView.as_view(), name='dashboard'),
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/nuevo/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/<int:pk>/activar/', views.UsuarioToggleActivoView.as_view(), name='usuario_toggle_activo'),
    path('usuarios/bulk/', views.UsuarioBulkToggleView.as_view(), name='usuario_bulk_toggle'),
    path('usuarios/<int:pk>/eliminar/', views.UsuarioDeleteView.as_view(), name='usuario_delete'),
    path('usuarios/<int:pk>/password/', views.CambiarPasswordOtroView.as_view(), name='usuario_cambiar_password'),
    path('perfil/', views.MiPerfilView.as_view(), name='perfil'),
    path('perfil/password/', views.CambiarMiPasswordView.as_view(), name='cambiar_mi_password'),
    path('perfil/timezone/', views.ActualizarTimezoneView.as_view(), name='actualizar_timezone'),
]
