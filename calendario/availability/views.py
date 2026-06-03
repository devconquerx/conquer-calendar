from datetime import date, datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView

from calendario.permisos.mixins import RequierePermisoMixin
from calendario.users.forms import TIMEZONE_CHOICES
from .forms import BloqueHorarioSemanalForm
from .models import BloqueHorarioSemanal, BloqueHorarioFecha


class _BloqueaDisponibilidadMixin:
    """Bloquea escritura si el grupo del host tiene bloquear_editar_disponibilidad=True.
    El magic login (supervisor actuando como host) bypasea el bloqueo."""
    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            from calendario.grupos.utils import usuario_bloqueado
            if usuario_bloqueado(request.user, 'bloquear_editar_disponibilidad', request):
                messages.error(request, 'Tu grupo no te autoriza para modificar la disponibilidad.')
                return redirect('panel_disponibilidad:bloque_list')
        return super().dispatch(request, *args, **kwargs)


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

        hoy = timezone.localdate()
        fechas_qs = BloqueHorarioFecha.objects.filter(
            host=self.request.user, fecha__gte=hoy
        ).order_by('fecha', 'hora_inicio')
        fechas_agrupadas = []
        for bloque in fechas_qs:
            if fechas_agrupadas and fechas_agrupadas[-1]['fecha'] == bloque.fecha:
                fechas_agrupadas[-1]['bloques'].append(bloque)
            else:
                fechas_agrupadas.append({'fecha': bloque.fecha, 'bloques': [bloque]})
        ctx['fechas_agrupadas'] = fechas_agrupadas

        # Datos JSON para la vista de calendario mensual (JS).
        # Semanal: {weekday(0=lunes): [[ini, fin], ...]}
        ctx['horas_semanales_json'] = {
            grupo['dia_valor']: [
                [b.hora_inicio.strftime('%H:%M'), b.hora_fin.strftime('%H:%M')]
                for b in grupo['bloques']
            ]
            for grupo in agrupados
        }
        # Overrides: {"YYYY-MM-DD": [[ini, fin], ...]}
        ctx['overrides_json'] = {
            grupo['fecha'].isoformat(): [
                [b.hora_inicio.strftime('%H:%M'), b.hora_fin.strftime('%H:%M')]
                for b in grupo['bloques']
            ]
            for grupo in fechas_agrupadas
        }
        return ctx


class BloqueHorarioCreateView(_BloqueaDisponibilidadMixin, RequierePermisoMixin, CreateView):
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


class BloqueHorarioDeleteView(_BloqueaDisponibilidadMixin, RequierePermisoMixin, DeleteView):
    permiso_requerido = 'availability.editar'
    model = BloqueHorarioSemanal
    template_name = 'pages/panel/disponibilidad/confirm_delete.html'
    success_url = reverse_lazy('panel_disponibilidad:bloque_list')

    def get_queryset(self):
        return BloqueHorarioSemanal.objects.filter(host=self.request.user)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Bloque horario eliminado.")
        return super().post(request, *args, **kwargs)


class LimpiarDiaView(_BloqueaDisponibilidadMixin, RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, dia):
        BloqueHorarioSemanal.objects.filter(
            host=request.user,
            dia_semana=dia,
        ).delete()
        return redirect('panel_disponibilidad:bloque_list')


def _parse_time(valor):
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(valor, fmt).time()
        except (ValueError, TypeError):
            continue
    return None


class BloqueHorarioFechaCreateView(_BloqueaDisponibilidadMixin, RequierePermisoMixin, View):
    """
    Asigna horas específicas a una o varias fechas. Las horas asignadas
    SOBRESCRIBEN cualquier override previo de esas fechas. Recibe:
      - fechas: ISO (YYYY-MM-DD) separadas por coma
      - hora_inicio[] / hora_fin[]: rangos paralelos
    """
    permiso_requerido = 'availability.editar'

    def post(self, request):
        fechas_raw = request.POST.get('fechas', '')
        fechas = []
        for token in fechas_raw.split(','):
            token = token.strip()
            if not token:
                continue
            try:
                fechas.append(date.fromisoformat(token))
            except ValueError:
                continue

        inicios = request.POST.getlist('hora_inicio')
        fines = request.POST.getlist('hora_fin')
        rangos = []
        for ini_raw, fin_raw in zip(inicios, fines):
            ini = _parse_time(ini_raw)
            fin = _parse_time(fin_raw)
            if ini is None or fin is None:
                continue
            rangos.append((ini, fin))

        if not fechas or not rangos:
            messages.error(request, "Selecciona al menos una fecha y un rango horario.")
            return redirect('panel_disponibilidad:bloque_list')

        for ini, fin in rangos:
            if fin <= ini:
                messages.error(request, "La hora de fin debe ser posterior a la de inicio.")
                return redirect('panel_disponibilidad:bloque_list')
        rangos_ord = sorted(rangos)
        for (_, fin_prev), (ini_sig, _) in zip(rangos_ord, rangos_ord[1:]):
            if ini_sig < fin_prev:
                messages.error(request, "Los rangos horarios se solapan entre sí.")
                return redirect('panel_disponibilidad:bloque_list')

        with transaction.atomic():
            for fecha in fechas:
                BloqueHorarioFecha.objects.filter(host=request.user, fecha=fecha).delete()
                for ini, fin in rangos_ord:
                    BloqueHorarioFecha.objects.create(
                        host=request.user, fecha=fecha, hora_inicio=ini, hora_fin=fin,
                    )

        plural = 's' if len(fechas) > 1 else ''
        messages.success(request, f"Horario específico guardado para {len(fechas)} fecha{plural}.")
        return redirect('panel_disponibilidad:bloque_list')


class BloqueHorarioFechaDeleteView(_BloqueaDisponibilidadMixin, RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, pk):
        BloqueHorarioFecha.objects.filter(host=request.user, pk=pk).delete()
        messages.success(request, "Bloque horario eliminado.")
        return redirect('panel_disponibilidad:bloque_list')


class LimpiarFechaView(_BloqueaDisponibilidadMixin, RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, fecha):
        try:
            fecha_obj = date.fromisoformat(fecha)
        except ValueError:
            return redirect('panel_disponibilidad:bloque_list')
        BloqueHorarioFecha.objects.filter(host=request.user, fecha=fecha_obj).delete()
        messages.success(request, "Horario específico eliminado.")
        return redirect('panel_disponibilidad:bloque_list')
