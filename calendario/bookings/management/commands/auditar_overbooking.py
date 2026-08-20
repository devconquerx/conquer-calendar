import json
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from calendario.bookings.models import Reserva
from calendario.event_types.models import EventType, EventTypeXHost
from calendario.google_calendar.models import GoogleCalendarEvento
from calendario.google_calendar.services import titulo_libera_horario

# Caracteres invisibles que se cuelan al copiar/pegar emojis desde Google
# Calendar (zero-width space, joiners, variation selector...). Una regla que
# los lleve dentro nunca matchea un título escrito a mano, así que los
# ignoramos SOLO para detectar el problema, nunca para decidir disponibilidad.
INVISIBLES = '​‌‍️⁠'


def _sin_invisibles(texto):
    return ''.join(c for c in (texto or '') if c not in INVISIBLES)


class Command(BaseCommand):
    help = (
        'Audita las reglas free/busy: lista los huecos que las reglas de un tipo '
        'de evento deberían abrir y que siguen bloqueados. Solo lectura. '
        'Pensado para comparar un antes/después (--salida fichero.json).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=45,
                            help='Ventana a auditar desde ahora (default: 45)')
        parser.add_argument('--salida', type=str, default='',
                            help='Ruta donde volcar el informe en JSON')
        parser.add_argument('--event-type', type=int, default=None,
                            help='Auditar solo este tipo de evento')

    def handle(self, *args, **opts):
        ahora = timezone.now()
        hasta = ahora + timedelta(days=opts['dias'])

        tipos = EventType.objects.filter(activo=True)
        if opts['event_type']:
            tipos = tipos.filter(pk=opts['event_type'])

        # Universo de marcas que el equipo usa como "liberadoras" en cualquier
        # tipo. Sirve para detectar reglas que faltan en un tipo concreto.
        universo = set()
        for et in EventType.objects.exclude(gcal_palabras_ignorar=''):
            for p in et.gcal_palabras_ignorar_lista:
                if _sin_invisibles(p).strip():
                    universo.add(_sin_invisibles(p).strip())

        gids_de_reservas = set(
            Reserva.objects
            .exclude(google_event_id='').exclude(google_event_id=None)
            .values_list('google_event_id', flat=True)
        )

        informe = {
            'generado': ahora.isoformat(),
            'ventana_dias': opts['dias'],
            'universo_marcas': sorted(universo),
            'tipos': [],
        }
        tot_reservas = tot_eventos = 0

        for et in tipos.order_by('pk'):
            palabras = et.gcal_palabras_ignorar_lista
            hosts = [x.host for x in
                     EventTypeXHost.objects.filter(event_type=et).select_related('host')]
            if not hosts:
                continue
            palabras_limpias = {_sin_invisibles(p).strip().casefold()
                                for p in palabras if _sin_invisibles(p).strip()}

            # Caso 1 (bug de código): reservas nuestras cuyo título SÍ matchea las
            # reglas del tipo consultado, pero que bloquean igual porque el flag
            # permite_overbooking se calculó con las reglas del tipo de la reserva.
            reservas_atrapadas = []
            # Caso 2 (configuración): eventos que bloquean y llevan una marca que
            # otros tipos sí reconocen, pero este no.
            eventos_sin_regla = []

            for host in hosts:
                eventos = {
                    e.google_event_id: e
                    for e in GoogleCalendarEvento.objects
                    .filter(host=host, inicio_utc__lt=hasta, fin_utc__gt=ahora)
                    .exclude(estado='cancelled')
                }

                for r in (Reserva.objects
                          .filter(host=host, estado=Reserva.Estado.CONFIRMADA,
                                  inicio_utc__lt=hasta, fin_utc__gt=ahora,
                                  permite_overbooking=False)
                          .select_related('event_type')):
                    ev = eventos.get(r.google_event_id)
                    if ev and titulo_libera_horario(ev.titulo, palabras):
                        reservas_atrapadas.append({
                            'reserva_id': r.pk,
                            'host': host.email,
                            'inicio_utc': r.inicio_utc.isoformat(),
                            'titulo': ev.titulo,
                            'event_type_reserva': r.event_type_id,
                            'nombre_event_type_reserva': r.event_type.nombre,
                            'reglas_event_type_reserva': r.event_type.gcal_palabras_ignorar_lista,
                        })

                for ev in eventos.values():
                    if ev.transparencia != 'opaque':
                        continue
                    if titulo_libera_horario(ev.titulo, palabras):
                        continue
                    t = _sin_invisibles(ev.titulo).casefold()
                    faltan = sorted({u for u in universo
                                     if u.casefold() in t
                                     and u.casefold() not in palabras_limpias})
                    if not faltan:
                        continue
                    eventos_sin_regla.append({
                        'host': host.email,
                        'google_event_id': ev.google_event_id,
                        'inicio_utc': ev.inicio_utc.isoformat(),
                        'horas': round((ev.fin_utc - ev.inicio_utc).total_seconds() / 3600, 2),
                        'titulo': ev.titulo,
                        'marcas_no_reconocidas': faltan,
                        'origen': ('app' if ev.google_event_id in gids_de_reservas
                                   else 'calendly_o_externo'),
                    })

            if not reservas_atrapadas and not eventos_sin_regla:
                continue

            tot_reservas += len(reservas_atrapadas)
            tot_eventos += len(eventos_sin_regla)
            informe['tipos'].append({
                'event_type': et.pk,
                'nombre': et.nombre,
                'reglas': palabras,
                'hosts': len(hosts),
                'reservas_atrapadas_por_el_flag': sorted(
                    reservas_atrapadas, key=lambda d: d['inicio_utc']),
                'eventos_con_marca_no_reconocida': sorted(
                    eventos_sin_regla, key=lambda d: d['inicio_utc']),
            })

        informe['total_reservas_atrapadas_por_el_flag'] = tot_reservas
        informe['total_eventos_con_marca_no_reconocida'] = tot_eventos

        self.stdout.write(
            f"Ventana: {opts['dias']} días desde {ahora:%Y-%m-%d %H:%M} UTC")
        self.stdout.write(
            f"Tipos de evento afectados: {len(informe['tipos'])}")
        self.stdout.write(self.style.WARNING(
            f"Reservas nuestras atrapadas por el flag (bug de código): {tot_reservas}"))
        self.stdout.write(self.style.WARNING(
            f"Eventos con marca que el tipo no reconoce (configuración): {tot_eventos}"))
        for t in informe['tipos']:
            n1 = len(t['reservas_atrapadas_por_el_flag'])
            n2 = len(t['eventos_con_marca_no_reconocida'])
            self.stdout.write(
                f"  ET{t['event_type']:<4d} flag={n1:<4d} config={n2:<4d} {t['nombre']}")

        if opts['salida']:
            with open(opts['salida'], 'w', encoding='utf-8') as fh:
                json.dump(informe, fh, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Informe escrito en {opts['salida']}"))
