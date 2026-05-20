from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView

from calendario.permisos.mixins import RequierePermisoMixin
from calendario.users.models import User
from .models import Reserva
from .services import cancelar_reserva, eliminar_reserva


class ReservaListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'reservas.ver_propias'
    model = Reserva
    template_name = 'pages/panel/reservas/list.html'
    context_object_name = 'reservas'
    paginate_by = 25

    def get_queryset(self):
        # Creador ve todas las reservas de sus eventos + las propias de eventos ajenos
        return (Reserva.objects
                .filter(
                    Q(event_type__host=self.request.user) |
                    Q(host=self.request.user)
                )
                .select_related('event_type', 'host')
                .distinct()
                .order_by('-inicio_utc'))


class ReservaDetailView(RequierePermisoMixin, DetailView):
    permiso_requerido = 'reservas.ver_propias'
    model = Reserva
    template_name = 'pages/panel/reservas/detail.html'
    context_object_name = 'reserva'

    def get_queryset(self):
        qs = Reserva.objects.select_related('event_type', 'host')
        if self.request.user.tiene_permiso('reservas.ver_todas'):
            return qs
        return qs.filter(host=self.request.user)


class ReservaAdminListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'reservas.ver_todas'
    model = Reserva
    template_name = 'pages/panel/reservas/admin_list.html'
    context_object_name = 'reservas'
    paginate_by = 25

    def get_queryset(self):
        qs = (Reserva.objects
              .select_related('event_type', 'host')
              .order_by('-inicio_utc'))
        host_id = self.request.GET.get('host', '').strip()
        email = self.request.GET.get('email', '').strip()
        estado = self.request.GET.get('estado', '').strip()
        if host_id:
            qs = qs.filter(host_id=host_id)
        if email:
            qs = qs.filter(email_invitado__icontains=email)
        if estado in ('confirmada', 'cancelada'):
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hosts'] = User.objects.filter(is_active=True).order_by('email')
        ctx['filtro_host'] = self.request.GET.get('host', '')
        ctx['filtro_email'] = self.request.GET.get('email', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', '')
        return ctx


class ReservaEliminarView(RequierePermisoMixin, View):
    permiso_requerido = 'reservas.cancelar'

    def post(self, request, pk):
        qs = Reserva.objects.all() if request.user.tiene_permiso('reservas.ver_todas') else Reserva.objects.filter(host=request.user)
        reserva = get_object_or_404(qs, pk=pk)
        nombre = reserva.nombre_invitado
        eliminar_reserva(reserva)
        messages.success(request, f"Reserva de '{nombre}' eliminada.")
        volver = 'panel_reservas:reserva_admin_list' if request.user.tiene_permiso('reservas.ver_todas') else 'panel_reservas:reserva_list'
        return redirect(volver)
