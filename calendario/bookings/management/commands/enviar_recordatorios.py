from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand

from calendario.bookings.correos import _enviar, resolver_config
from calendario.bookings.models import Reserva


class Command(BaseCommand):
    help = 'Envía recordatorios de reservas próximas. Diseñado para ejecutarse cada 5 minutos via cron.'

    def handle(self, *args, **options):
        ahora = datetime.now(timezone.utc)
        enviados = 0
        errores = 0

        reservas = (
            Reserva.objects
            .filter(estado=Reserva.Estado.CONFIRMADA, inicio_utc__gt=ahora)
            .select_related(
                'event_type__config_correo__plantilla_recordatorio',
                'host',
            )
            .prefetch_related('host__membresias_grupo__grupo__config_correo__plantilla_recordatorio')
        )

        for reserva in reservas:
            plantilla, _ = resolver_config(reserva, 'recordatorio')
            if not plantilla:
                continue

            tiempo_restante = reserva.inicio_utc - ahora

            # Recordatorio 1
            if (
                plantilla.recordatorio_1_activo
                and not reserva.recordatorio_1_enviado
                and tiempo_restante <= timedelta(hours=plantilla.recordatorio_1_horas)
            ):
                ok = _enviar(reserva, 'recordatorio_1', reserva.email_invitado, plantilla)
                _enviar(reserva, 'recordatorio_1', reserva.host.email, plantilla)
                Reserva.objects.filter(pk=reserva.pk).update(recordatorio_1_enviado=True)
                if ok:
                    enviados += 1
                else:
                    errores += 1

            # Recordatorio 2
            if (
                plantilla.recordatorio_2_activo
                and not reserva.recordatorio_2_enviado
                and tiempo_restante <= timedelta(hours=plantilla.recordatorio_2_horas)
            ):
                ok = _enviar(reserva, 'recordatorio_2', reserva.email_invitado, plantilla)
                _enviar(reserva, 'recordatorio_2', reserva.host.email, plantilla)
                Reserva.objects.filter(pk=reserva.pk).update(recordatorio_2_enviado=True)
                if ok:
                    enviados += 1
                else:
                    errores += 1

        self.stdout.write(
            self.style.SUCCESS(f'Recordatorios procesados: {enviados} enviados, {errores} errores.')
        )
