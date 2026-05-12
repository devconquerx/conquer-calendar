from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView

from calendario.permisos.mixins import RequierePermisoMixin
from calendario.users.forms import TIMEZONE_CHOICES
from .forms import BloqueHorarioSemanalForm
from .models import BloqueHorarioSemanal


class MiDisponibilidadListView(RequierePermisoMixin, ListView):
    permiso_requerido = 'availability.ver'
    model = BloqueHorarioSemanal
    template_name = 'pages/panel/disponibilidad/list.html'
    context_object_name = 'bloques'

    def get_queryset(self):
        return BloqueHorarioSemanal.objects.filter(
            host=self.request.user
        ).order_by('dia_semana', 'hora_inicio')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bloques = list(ctx['bloques'])
        agrupados = []
        for valor, etiqueta in BloqueHorarioSemanal.DiaSemana.choices:
            agrupados.append({
                'dia_valor': valor,
                'dia_etiqueta': etiqueta,
                'bloques': [b for b in bloques if b.dia_semana == valor],
            })
        ctx['dias_agrupados'] = agrupados
        ctx['timezone_choices'] = TIMEZONE_CHOICES
        return ctx


class BloqueHorarioCreateView(RequierePermisoMixin, CreateView):
    permiso_requerido = 'availability.editar'
    model = BloqueHorarioSemanal
    form_class = BloqueHorarioSemanalForm
    template_name = 'pages/panel/disponibilidad/form.html'
    success_url = reverse_lazy('panel_disponibilidad:bloque_list')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.host = self.request.user
        try:
            obj.full_clean()
        except ValidationError as e:
            for field, errs in e.message_dict.items():
                for err in errs:
                    form.add_error(field if field != '__all__' else None, err)
            return self.form_invalid(form)
        obj.save()
        self.object = obj
        messages.success(self.request, "Bloque horario añadido.")
        return redirect(self.get_success_url())


class BloqueHorarioDeleteView(RequierePermisoMixin, DeleteView):
    permiso_requerido = 'availability.editar'
    model = BloqueHorarioSemanal
    template_name = 'pages/panel/disponibilidad/confirm_delete.html'
    success_url = reverse_lazy('panel_disponibilidad:bloque_list')

    def get_queryset(self):
        return BloqueHorarioSemanal.objects.filter(host=self.request.user)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Bloque horario eliminado.")
        return super().post(request, *args, **kwargs)


class LimpiarDiaView(RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, dia):
        BloqueHorarioSemanal.objects.filter(
            host=request.user,
            dia_semana=dia,
        ).delete()
        return redirect('panel_disponibilidad:bloque_list')
