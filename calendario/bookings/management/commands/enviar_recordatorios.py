import time
from datetime import datetime, timezone, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from calendario.bookings.correos import _enviar, resolver_config
from calendario.bookings.models import Reserva


# Tras varios fallos seguidos dejamos de insistir: si una dirección está rota,
# reintentarla cada 5 minutos hasta que empiece la sesión solo gasta cuota.
MAX_INTENTOS = 5

# Mailgun corta las ráfagas (con la cuenta en probation, ~26 destinatarios
# seguidos). Soltar los recordatorios a cuentagotas evita el rebote; lo que no
# entre en esta pasada sale en la siguiente, 5 minutos después.
MAX_POR_EJECUCION = 20
PAUSA_ENTRE_ENVIOS = 0.5


class Command(BaseCommand):
    help = 'Envía recordatorios de reservas próximas. Diseñado para ejecutarse cada 5 minutos via cron.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite',
            type=int,
            default=getattr(settings, 'CALENDARIO_RECORDATORIOS_MAX_POR_EJECUCION', MAX_POR_EJECUCION),
            help='Máximo de correos por ejecución. 0 = sin límite.',
        )
        parser.add_argument(
            '--pausa',
            type=float,
            default=getattr(settings, 'CALENDARIO_RECORDATORIOS_PAUSA', PAUSA_ENTRE_ENVIOS),
            help='Segundos de espera entre correos, para no disparar el límite de ráfaga.',
        )

    def handle(self, *args, **options):
        ahora = datetime.now(timezone.utc)
        limite = options['limite']
        pausa = options['pausa']

        enviados = 0
        errores = 0
        pendientes = False

        reservas = (
            Reserva.objects
            .filter(estado=Reserva.Estado.CONFIRMADA, inicio_utc__gt=ahora)
            .select_related(
                'event_type__config_correo__plantilla_recordatorio__dominio',
                'host',
            )
            .prefetch_related('host__membresias_grupo__grupo__config_correo__plantilla_recordatorio__dominio')
            # Lo más inminente primero: si el límite corta la pasada, que se
            # queden fuera los de 24h y no los de 1h.
            .order_by('inicio_utc')
        )

        for reserva in reservas:
            if limite and enviados + errores >= limite:
                pendientes = True
                break

            plantilla, _ = resolver_config(reserva, 'recordatorio')
            if not plantilla:
                continue

            tiempo_restante = reserva.inicio_utc - ahora

            for n in (1, 2):
                if limite and enviados + errores >= limite:
                    pendientes = True
                    break

                activo = getattr(plantilla, f'recordatorio_{n}_activo')
                horas = getattr(plantilla, f'recordatorio_{n}_horas')
                ya_enviado = getattr(reserva, f'recordatorio_{n}_enviado')
                intentos = getattr(reserva, f'recordatorio_{n}_intentos')

                if not activo or ya_enviado or intentos >= MAX_INTENTOS:
                    continue
                if tiempo_restante > timedelta(hours=horas):
                    continue

                ok = _enviar(reserva, f'recordatorio_{n}', reserva.email_invitado, plantilla)

                if ok:
                    # Solo se marca como enviado si salió de verdad. Antes se
                    # marcaba pasara lo que pasara y el correo se perdía.
                    Reserva.objects.filter(pk=reserva.pk).update(
                        **{f'recordatorio_{n}_enviado': True}
                    )
                    enviados += 1
                else:
                    Reserva.objects.filter(pk=reserva.pk).update(
                        **{f'recordatorio_{n}_intentos': intentos + 1}
                    )
                    errores += 1

                if pausa:
                    time.sleep(pausa)

        resumen = f'Recordatorios procesados: {enviados} enviados, {errores} errores.'
        if pendientes:
            resumen += ' Quedan pendientes para la siguiente ejecución.'
        self.stdout.write(self.style.SUCCESS(resumen))
