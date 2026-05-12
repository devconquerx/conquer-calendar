from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from datetime import timedelta

from django.utils import timezone

from calendario.bookings.models import Reserva
from calendario.event_types.models import EventType
from calendario.permisos.mixins import RequierePermisoMixin
from calendario.users.forms import (
    CambiarMiPasswordForm,
    CambiarPasswordOtroForm,
    MiPerfilForm,
    TimezoneForm,
    UsuarioCreacionForm,
    UsuarioEdicionForm,
)
from calendario.users.models import User


class PanelDashboardView(RequierePermisoMixin, TemplateView):
    permiso_requerido = 'panel.acceder'
    template_name = 'pages/panel/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        hoy_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
        semana_inicio = hoy_inicio - timedelta(days=hoy_inicio.weekday())

        confirmadas = Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA)
        ctx.update({
            'page_title': 'Dashboard',
            'reservas_hoy': confirmadas.filter(
                inicio_utc__gte=hoy_inicio,
                inicio_utc__lt=hoy_inicio + timedelta(days=1),
            ).count(),
            'reservas_semana': confirmadas.filter(
                inicio_utc__gte=semana_inicio,
                inicio_utc__lt=semana_inicio + timedelta(days=7),
            ).count(),
            'event_types_activos': EventType.objects.filter(activo=True).count(),
            'hosts_activos': User.objects.filter(is_active=True).count(),
            'proximas_reservas': (
                confirmadas
                .filter(inicio_utc__gte=now)
                .select_related('host', 'event_type')
                .order_by('inicio_utc')[:10]
            ),
        })
        return ctx


class UsuarioListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'usuarios.ver'
    model = User
    template_name = 'pages/panel/usuarios/list.html'
    context_object_name = 'usuarios'
    paginate_by = 25
    ordering = ['email']

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('roles_asignados__rol')
        dominio = self.request.GET.get('dominio', '').strip()
        estado = self.request.GET.get('estado', '').strip()
        if dominio:
            qs = qs.filter(email__iendswith=f'@{dominio}')
        if estado == 'activo':
            qs = qs.filter(is_active=True)
        elif estado == 'inactivo':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dominios = (
            User.objects.values_list('email', flat=True)
            .order_by('email')
        )
        dominio_set = sorted({e.split('@')[1] for e in dominios if '@' in e})
        ctx['dominios'] = dominio_set
        ctx['filtro_dominio'] = self.request.GET.get('dominio', '')
        ctx['filtro_estado'] = self.request.GET.get('estado', '')
        return ctx


class UsuarioBulkToggleView(RequierePermisoMixin, View):
    permiso_requerido = 'usuarios.activar'

    def post(self, request):
        accion = request.POST.get('accion')
        ids = request.POST.getlist('ids')
        if not ids or accion not in ('activar', 'desactivar'):
            messages.error(request, "Acción no válida.")
            return redirect('panel_usuarios:usuario_list')

        qs = User.objects.filter(pk__in=ids).exclude(pk=request.user.pk)
        activo = accion == 'activar'
        cantidad = qs.update(is_active=activo)
        verbo = "activados" if activo else "desactivados"
        messages.success(request, f"{cantidad} usuario(s) {verbo}.")
        return redirect(request.POST.get('next', 'panel_usuarios:usuario_list'))


class UsuarioCreateView(RequierePermisoMixin, CreateView):
    permiso_requerido = 'usuarios.crear'
    model = User
    form_class = UsuarioCreacionForm
    template_name = 'pages/panel/usuarios/form.html'
    success_url = reverse_lazy('panel_usuarios:usuario_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Usuario {self.object.username} creado correctamente.")
        return response


class UsuarioUpdateView(RequierePermisoMixin, UpdateView):
    permiso_requerido = 'usuarios.editar'
    model = User
    form_class = UsuarioEdicionForm
    template_name = 'pages/panel/usuarios/form.html'
    success_url = reverse_lazy('panel_usuarios:usuario_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Usuario {self.object.username} actualizado correctamente.")
        return response


class UsuarioToggleActivoView(RequierePermisoMixin, View):
    permiso_requerido = 'usuarios.activar'

    def post(self, request, pk):
        obj = get_object_or_404(User, pk=pk)
        if obj == request.user:
            messages.error(request, "No puedes desactivar tu propia cuenta.")
            return redirect('panel_usuarios:usuario_list')
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active', 'fecha_actualizacion'])
        estado = "activado" if obj.is_active else "desactivado"
        messages.success(request, f"Usuario {obj.username} {estado}.")
        return redirect('panel_usuarios:usuario_list')


class UsuarioDeleteView(RequierePermisoMixin, DeleteView):
    permiso_requerido = 'usuarios.eliminar'
    model = User
    template_name = 'pages/panel/usuarios/confirm_delete.html'
    success_url = reverse_lazy('panel_usuarios:usuario_list')

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj == request.user:
            messages.error(request, "No puedes eliminar tu propia cuenta.")
            return redirect('panel_usuarios:usuario_list')
        if obj.is_superuser:
            messages.error(request, "No se puede eliminar un superusuario.")
            return redirect('panel_usuarios:usuario_list')
        messages.success(request, f"Usuario {obj.username} eliminado.")
        return super().post(request, *args, **kwargs)


class CambiarPasswordOtroView(RequierePermisoMixin, FormView):
    permiso_requerido = 'usuarios.cambiar_password'
    form_class = CambiarPasswordOtroForm
    template_name = 'pages/panel/usuarios/cambiar_password.html'

    def get_objeto(self):
        return get_object_or_404(User, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['objeto'] = self.get_objeto()
        return ctx

    def form_valid(self, form):
        user = self.get_objeto()
        user.set_password(form.cleaned_data['password1'])
        user.save()
        messages.success(self.request, f"Password de {user.username} actualizado.")
        return redirect('panel_usuarios:usuario_list')


class MiPerfilView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = MiPerfilForm
    template_name = 'pages/panel/perfil/index.html'

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Perfil actualizado correctamente.")
        return redirect('panel_usuarios:perfil')


class ActualizarTimezoneView(LoginRequiredMixin, View):
    def post(self, request):
        form = TimezoneForm(request.POST)
        if form.is_valid():
            request.user.timezone = form.cleaned_data['timezone']
            request.user.save(update_fields=['timezone'])
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
        return redirect(next_url)


class CambiarMiPasswordView(LoginRequiredMixin, FormView):
    form_class = CambiarMiPasswordForm
    template_name = 'pages/panel/usuarios/cambiar_password.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        user.set_password(form.cleaned_data['password1'])
        user.save()
        update_session_auth_hash(self.request, user)
        messages.success(self.request, "Password actualizado. Sigue conectado.")
        return redirect('panel_usuarios:dashboard')
