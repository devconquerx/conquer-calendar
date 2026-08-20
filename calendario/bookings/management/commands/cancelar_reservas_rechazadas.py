from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from calendario.bookings.models import Reserva
from calendario.bookings.services import cancelar_reserva
from calendario.google_calendar.models import (
    GoogleCalendarEvento, GoogleCalendarSyncEstado,
)
from calendario.google_calendar.services import obtener_servicio_calendar
from calendario.google_calendar.sync import _host_declino


class Command(BaseCommand):
    help = (
        'Cancela las reservas que siguen confirmadas en la app pero que el host '
        'ya rechazó o canceló en Google Calendar. Resuelve el arrastre anterior '
        'a que el sync lo hiciera solo. POR DEFECTO NO ESCRIBE NADA: hay que '
        'pasar --aplicar. Cancelar avisa al invitado por Google (sendUpdates=all).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=90,
                            help='Ventana hacia adelante a revisar (default: 90)')
        parser.add_argument('--aplicar', action='store_true',
                            help='Cancela de verdad. Sin esto solo enseña qué haría.')
        parser.add_argument('--limite', type=int, default=0,
                            help='Procesar como mucho N reservas (0 = sin límite)')
        parser.add_argument('--host', type=str, default='',
                            help='Limitar a un host por email')
        parser.add_argument('--incluir-invitado-declinado', action='store_true',
                            help='Cancelar también cuando quien rechazó fue el invitado')

    def handle(self, *args, **opts):
        ahora = timezone.now()
        hasta = ahora + timedelta(days=opts['dias'])

        # Solo hosts con sync activo: si no lo tienen, que el evento no esté en la
        # copia local no significa nada.
        hosts_ok = set(GoogleCalendarSyncEstado.objects
                       .filter(estado=GoogleCalendarSyncEstado.ACTIVO)
                       .values_list('host_id', flat=True))

        qs = (Reserva.objects
              .filter(estado=Reserva.Estado.CONFIRMADA,
                      inicio_utc__gte=ahora, inicio_utc__lt=hasta)
              .exclude(google_event_id='').exclude(google_event_id=None)
              .select_related('host', 'event_type')
              .order_by('inicio_utc'))
        if opts['host']:
            qs = qs.filter(host__email=opts['host'])

        # Candidatas: su evento ya no está en la copia local. El sync borra de ahí
        # lo cancelado y lo rechazado por el host, así que esto los recoge todos.
        # Se confirma uno a uno contra Google antes de tocar nada.
        candidatas = [
            r for r in qs
            if r.host_id in hosts_ok
            and not GoogleCalendarEvento.objects.filter(
                host_id=r.host_id, google_event_id=r.google_event_id).exists()
        ]
        self.stdout.write(f"Candidatas a revisar contra Google: {len(candidatas)}")

        servicios = {}
        a_cancelar, descartadas = [], []
        for r in candidatas:
            try:
                if r.host_id not in servicios:
                    servicios[r.host_id] = obtener_servicio_calendar(r.host.email)
                item = servicios[r.host_id].events().get(
                    calendarId='primary', eventId=r.google_event_id).execute()
                invitados = [a for a in item.get('attendees', []) if not a.get('self')]
                invitado_declino = bool(invitados) and all(
                    a.get('responseStatus') == 'declined' for a in invitados)
                if item.get('status') == 'cancelled':
                    a_cancelar.append((r, 'evento cancelado en Google'))
                elif _host_declino(item):
                    a_cancelar.append((r, 'el host rechazó la invitación'))
                elif invitado_declino and opts['incluir_invitado_declinado']:
                    a_cancelar.append((r, 'el invitado rechazó la invitación'))
                else:
                    descartadas.append((r, 'sigue activo en Google'))
            except Exception as e:
                codigo = getattr(getattr(e, 'resp', None), 'status', None)
                if codigo == 404:
                    a_cancelar.append((r, 'evento borrado en Google'))
                else:
                    descartadas.append((r, f'no se pudo consultar ({codigo or e.__class__.__name__})'))

        if opts['limite']:
            a_cancelar = a_cancelar[:opts['limite']]

        self.stdout.write('')
        self.stdout.write(f"A cancelar: {len(a_cancelar)}   |   descartadas: {len(descartadas)}")
        for r, motivo in a_cancelar:
            self.stdout.write(
                f"  {r.inicio_utc:%Y-%m-%d %H:%M}Z | reserva {r.pk} | ET{r.event_type_id} | "
                f"{r.host.email} | {r.nombre_invitado} <{r.email_invitado}> | {motivo}")

        if not opts['aplicar']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'SIMULACIÓN: no se ha tocado nada. Añade --aplicar para cancelarlas '
                '(el invitado recibirá el aviso de Google).'))
            return

        hechas = fallidas = 0
        for r, _motivo in a_cancelar:
            try:
                cancelar_reserva(r)
                hechas += 1
            except Exception as e:
                fallidas += 1
                self.stderr.write(f"  ERROR cancelando reserva {r.pk}: {e}")
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"Canceladas: {hechas}"))
        if fallidas:
            self.stdout.write(self.style.ERROR(f"Fallidas: {fallidas}"))
