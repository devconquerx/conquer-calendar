from django.urls import path
from . import views

app_name = 'panel_grupos'

urlpatterns = [
    path('', views.GrupoListView.as_view(), name='grupo_list'),
    path('nuevo/', views.GrupoCreateView.as_view(), name='grupo_create'),
    path('<int:pk>/editar/', views.GrupoUpdateView.as_view(), name='grupo_update'),
    path('<int:pk>/miembros/', views.GrupoMiembrosUpdateView.as_view(), name='grupo_miembros'),
    path('<int:pk>/permisos/', views.GrupoPermisosView.as_view(), name='grupo_permisos'),
    path('<int:pk>/eliminar/', views.GrupoDeleteView.as_view(), name='grupo_delete'),
]
