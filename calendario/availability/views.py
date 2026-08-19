from datetime import date, datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, DeleteView

from calendario.permisos.mixins import RequierePermisoMixin
from calendario.users.forms import TIMEZONE_CHOICES
from .forms import BloqueHorarioSemanalForm
from .models import BloqueHorarioSemanal, BloqueHorarioFecha


class HostObjetivoMixin:
    """
    Resuelve sobre qué host actúa la vista. Por defecto el propio usuario; con
    `?host=<pk>` (GET) o `host=<pk>` (POST) actúa sobre otro usuario, siempre
    que el que edita sea admin o supervisor de un grupo al que pertenezca.
    """

    @property
    def host_objetivo(self):
        if not hasattr(self, '_host_objetivo'):
            self._host_objetivo = self._resolver_host()
        return self._host_objetivo

    @property
    def editando_a_otro(self):
        return self.host_objetivo.pk != self.request.user.pk

    def _resolver_host(self):
        raw = self.request.POST.get('host') or self.request.GET.get('host')
        if not raw:
            return self.request.user
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            return self.request.user
        if pk == self.request.user.pk:
            return self.request.user

        from calendario.grupos.utils import hosts_editables
        host = hosts_editables(self.request.user).filter(pk=pk).first()
        if host is None:
            raise PermissionDenied("No puedes gestionar la disponibilidad de este usuario.")
        return host

    def url_lista(self):
        url = reverse('panel_disponibilidad:bloque_list')
        if self.editando_a_otro:
            url = f'{url}?host={self.host_objetivo.pk}'
        return url

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['host_objetivo'] = self.host_objetivo
        ctx['editando_a_otro'] = self.editando_a_otro
        return ctx


class _BloqueaDisponibilidadMixin:
    """Bloquea escritura si el grupo del host tiene bloquear_editar_disponibilidad=True.
    El magic login (supervisor actuando como host) bypasea el bloqueo, igual que
    editar la disponibilidad de otro usuario siendo admin/supervisor."""
    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and not self.editando_a_otro:
            from calendario.grupos.utils import usuario_bloqueado
            if usuario_bloqueado(request.user, 'bloquear_editar_disponibilidad', request):
                messages.error(request, 'Tu grupo no te autoriza para modificar la disponibilidad.')
                return redirect(self.url_lista())
        return super().dispatch(request, *args, **kwargs)


class MiDisponibilidadListView(HostObjetivoMixin, RequierePermisoMixin, ListView):
    permiso_requerido = 'availability.ver'
    model = BloqueHorarioSemanal
    template_name = 'pages/panel/disponibilidad/list.html'
    context_object_name = 'bloques'

    def get_queryset(self):
        return BloqueHorarioSemanal.objects.filter(
            host=self.host_objetivo
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
        ctx['dias_semana'] = BloqueHorarioSemanal.DiaSemana.choices
        ctx['timezone_choices'] = TIMEZONE_CHOICES

        hoy = timezone.localdate()
        fechas_qs = BloqueHorarioFecha.objects.filter(
            host=self.host_objetivo, fecha__gte=hoy
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

        # Selector "editar horario de" (admin / supervisor de grupo)
        from calendario.grupos.utils import hosts_editables
        editables = list(hosts_editables(self.request.user))
        ctx['puede_elegir_host'] = len(editables) > 1
        ctx['hosts_editables_json'] = [
            {
                'pk': u.pk,
                'nombre': u.nombre_display(),
                'email': u.email,
                'iniciales': _iniciales(u),
                'es_yo': u.pk == self.request.user.pk,
            }
            for u in editables
        ] if len(editables) > 1 else []
        ctx['host_iniciales'] = _iniciales(self.host_objetivo)
        return ctx


class BloqueHorarioCreateView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                              RequierePermisoMixin, CreateView):
    permiso_requerido = 'availability.editar'
    model = BloqueHorarioSemanal
    form_class = BloqueHorarioSemanalForm
    template_name = 'pages/panel/disponibilidad/form.html'

    def get_success_url(self):
        return self.url_lista()

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.host = self.host_objetivo
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


class BloqueHorarioUpdateView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                              RequierePermisoMixin, View):
    """Edición en línea de un bloque semanal: cambia las horas sin borrarlo."""
    permiso_requerido = 'availability.editar'

    def post(self, request, pk):
        bloque = BloqueHorarioSemanal.objects.filter(
            pk=pk, host=self.host_objetivo
        ).first()
        if bloque is None:
            raise Http404("Bloque horario no encontrado.")
        return _guardar_horas_en_linea(request, bloque, self.url_lista())


class CopiarDiaAOtrosDiasView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                              RequierePermisoMixin, View):
    """Copia el horario de un día a los días marcados, igual que Calendly.

    Se copian TODOS los rangos del día de origen y se REEMPLAZA lo que hubiera
    en cada destino, de forma que los días elegidos quedan idénticos al origen.
    """
    permiso_requerido = 'availability.editar'

    def post(self, request, dia):
        validos = {valor for valor, _ in BloqueHorarioSemanal.DiaSemana.choices}
        if dia not in validos:
            raise Http404("Día no válido.")

        origen = list(
            BloqueHorarioSemanal.objects.filter(host=self.host_objetivo, dia_semana=dia)
            .order_by('hora_inicio')
        )
        if not origen:
            messages.error(request, "Ese día no tiene horarios que copiar.")
            return redirect(self.url_lista())

        destinos = []
        for raw in request.POST.getlist('dias'):
            try:
                destino = int(raw)
            except (TypeError, ValueError):
                continue
            if destino in validos and destino != dia and destino not in destinos:
                destinos.append(destino)

        if not destinos:
            messages.error(request, "Selecciona al menos un día al que copiar el horario.")
            return redirect(self.url_lista())

        with transaction.atomic():
            BloqueHorarioSemanal.objects.filter(
                host=self.host_objetivo, dia_semana__in=destinos
            ).delete()
            BloqueHorarioSemanal.objects.bulk_create([
                BloqueHorarioSemanal(
                    host=self.host_objetivo,
                    dia_semana=destino,
                    hora_inicio=bloque.hora_inicio,
                    hora_fin=bloque.hora_fin,
                )
                for destino in destinos
                for bloque in origen
            ])

        etiqueta = BloqueHorarioSemanal.DiaSemana(dia).label.lower()
        plural = 's' if len(destinos) > 1 else ''
        messages.success(
            request, f"Horario del {etiqueta} copiado a {len(destinos)} día{plural}."
        )
        return redirect(self.url_lista())


class BloqueHorarioDeleteView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                              RequierePermisoMixin, DeleteView):
    permiso_requerido = 'availability.editar'
    model = BloqueHorarioSemanal
    template_name = 'pages/panel/disponibilidad/confirm_delete.html'

    def get_success_url(self):
        return self.url_lista()

    def get_queryset(self):
        return BloqueHorarioSemanal.objects.filter(host=self.host_objetivo)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Bloque horario eliminado.")
        return super().post(request, *args, **kwargs)


class LimpiarDiaView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                     RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, dia):
        BloqueHorarioSemanal.objects.filter(
            host=self.host_objetivo,
            dia_semana=dia,
        ).delete()
        return redirect(self.url_lista())


def _guardar_horas_en_linea(request, bloque, url_vuelta):
    """Aplica hora_inicio/hora_fin del POST a un bloque ya existente.

    Los errores (rango invertido, solape con otro bloque del mismo día o fecha)
    llegan como mensaje: la fila se recarga con los valores previos.
    """
    ini = _parse_time(request.POST.get('hora_inicio'))
    fin = _parse_time(request.POST.get('hora_fin'))
    if ini is None or fin is None:
        messages.error(request, "Las horas indicadas no son válidas.")
        return redirect(url_vuelta)

    if (ini, fin) == (bloque.hora_inicio, bloque.hora_fin):
        return redirect(url_vuelta)

    bloque.hora_inicio = ini
    bloque.hora_fin = fin
    try:
        bloque.full_clean()
    except ValidationError as e:
        for errores in e.message_dict.values():
            for error in errores:
                messages.error(request, error)
        return redirect(url_vuelta)

    bloque.save(update_fields=['hora_inicio', 'hora_fin', 'fecha_actualizacion'])
    messages.success(request, "Horario actualizado.")
    return redirect(url_vuelta)


def _iniciales(user):
    """Iniciales para el avatar del selector: 'Marco Ruiz' → 'MR'."""
    partes = [p for p in user.nombre_display().split() if p]
    if not partes:
        return (user.email[:1] or '?').upper()
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][:1] + partes[-1][:1]).upper()


def _parse_time(valor):
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(valor, fmt).time()
        except (ValueError, TypeError):
            continue
    return None


class BloqueHorarioFechaCreateView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                                   RequierePermisoMixin, View):
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
            return redirect(self.url_lista())

        for ini, fin in rangos:
            if fin <= ini:
                messages.error(request, "La hora de fin debe ser posterior a la de inicio.")
                return redirect(self.url_lista())
        rangos_ord = sorted(rangos)
        for (_, fin_prev), (ini_sig, _) in zip(rangos_ord, rangos_ord[1:]):
            if ini_sig < fin_prev:
                messages.error(request, "Los rangos horarios se solapan entre sí.")
                return redirect(self.url_lista())

        host = self.host_objetivo
        with transaction.atomic():
            for fecha in fechas:
                BloqueHorarioFecha.objects.filter(host=host, fecha=fecha).delete()
                for ini, fin in rangos_ord:
                    BloqueHorarioFecha.objects.create(
                        host=host, fecha=fecha, hora_inicio=ini, hora_fin=fin,
                    )

        plural = 's' if len(fechas) > 1 else ''
        messages.success(request, f"Horario específico guardado para {len(fechas)} fecha{plural}.")
        return redirect(self.url_lista())


class BloqueHorarioFechaUpdateView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                                   RequierePermisoMixin, View):
    """Edición en línea de un horario específico de una fecha."""
    permiso_requerido = 'availability.editar'

    def post(self, request, pk):
        bloque = BloqueHorarioFecha.objects.filter(
            pk=pk, host=self.host_objetivo
        ).first()
        if bloque is None:
            raise Http404("Horario específico no encontrado.")
        return _guardar_horas_en_linea(request, bloque, self.url_lista())


class BloqueHorarioFechaDeleteView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                                   RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, pk):
        BloqueHorarioFecha.objects.filter(host=self.host_objetivo, pk=pk).delete()
        messages.success(request, "Bloque horario eliminado.")
        return redirect(self.url_lista())


class LimpiarFechaView(HostObjetivoMixin, _BloqueaDisponibilidadMixin,
                       RequierePermisoMixin, View):
    permiso_requerido = 'availability.editar'

    def post(self, request, fecha):
        try:
            fecha_obj = date.fromisoformat(fecha)
        except ValueError:
            return redirect(self.url_lista())
        BloqueHorarioFecha.objects.filter(host=self.host_objetivo, fecha=fecha_obj).delete()
        messages.success(request, "Horario específico eliminado.")
        return redirect(self.url_lista())
