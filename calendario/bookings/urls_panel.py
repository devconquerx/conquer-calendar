from django.urls import path
from . import views_panel as v

app_name = 'panel_reservas'
urlpatterns = [
    path('', v.ReservaListView.as_view(), name='reserva_list'),
    path('todas/', v.ReservaAdminListView.as_view(), name='reserva_admin_list'),
    path('<int:pk>/', v.ReservaDetailView.as_view(), name='reserva_detail'),
    path('<int:pk>/eliminar/', v.ReservaEliminarView.as_view(), name='reserva_eliminar'),
]
