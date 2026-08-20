from django.urls import path
from . import views_panel as v

app_name = 'panel_reservas'
urlpatterns = [
    path('', v.ReservaListView.as_view(), name='reserva_list'),
    path('todas/', v.ReservaAdminListView.as_view(), name='reserva_admin_list'),
    path('cancelaciones/', v.CancelacionesListView.as_view(), name='cancelaciones'),
    path('<int:pk>/', v.ReservaDetailView.as_view(), name='reserva_detail'),
    path('<int:pk>/eliminar/', v.ReservaEliminarView.as_view(), name='reserva_eliminar'),
    path('<int:pk>/cancelar/', v.ReservaCancelarView.as_view(), name='reserva_cancelar'),
]
