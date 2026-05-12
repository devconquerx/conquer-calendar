from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView

from calendario.permisos.mixins import RequierePermisoMixin
from .models import Reserva
from .services import cancelar_reserva


class ReservaListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'reservas.ver_propias'
    model = Reserva
    template_name = 'pages/panel/reservas/list.html'
    context_object_name = 'reservas'
    paginate_by = 25

    def get_queryset(self):
        return (Reserva.objects
                .filter(host=self.request.user)
                .select_related('event_type')
                .order_by('-inicio_utc'))


class ReservaDetailView(RequierePermisoMixin, DetailView):
    permiso_requerido = 'reservas.ver_propias'
    model = Reserva
    template_name = 'pages/panel/reservas/detail.html'
    context_object_name = 'reserva'

    def get_queryset(self):
        return Reserva.objects.filter(host=self.request.user).select_related('event_type')


class ReservaCancelarView(RequierePermisoMixin, View):
    permiso_requerido = 'reservas.cancelar'

    def post(self, request, pk):
        reserva = get_object_or_404(Reserva, pk=pk, host=request.user)
        cancelar_reserva(reserva)
        messages.success(request, f"Reserva de '{reserva.nombre_invitado}' cancelada.")
        return redirect('panel_reservas:reserva_list')
