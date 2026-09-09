"""Reenvía a la academia sesiones que ya estaban agendadas.

Es una herramienta de recuperación, no de carga inicial: el histórico anterior a
la integración **no** se sube. Las sesiones se van registrando de aquí en
adelante, y esto existe para los huecos que dejen los fallos —una caída del LMS
más larga de lo que aguantan los reintentos de Celery y el barrido de 24 h, que
solo mira reservas recientes.

Por eso exige un rango explícito (`--desde`, y `--hasta` si hace falta): sin él
no hace nada. Un comando que por omisión manda todo lo que hay es justo el que
acaba subiendo cinco años de reservas a la academia sin que nadie lo pida.

Es idempotente: del otro lado es un upsert por `reservationId`, así que reenviar
lo mismo no duplica nada. Manda siempre el estado actual, de modo que una reserva
cancelada llega como cancelada aunque en su día se enviara confirmada.

    python manage.py enviar_sesiones_academia --desde 2026-09-10 --dry-run
    python manage.py enviar_sesiones_academia --desde 2026-09-10 --hasta 2026-09-12
    python manage.py enviar_sesiones_academia --desde 2026-09-10 --evento 12 --sincrono
"""
from datetime import datetime, time, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError

from calendario.bookings.models import Reserva


class Command(BaseCommand):
    help = 'Reenvía a la academia las reservas de los tipos de evento marcados con «registrar en la academia».'

    def add_arguments(self, parser):
        parser.add_argument(
            '--desde', type=str, default='',
            help='Fecha de inicio (YYYY-MM-DD), sobre el comienzo de la sesión. OBLIGATORIA.',
        )
        parser.add_argument(
            '--hasta', type=str, default='',
            help='Fecha de fin exclusiva (YYYY-MM-DD), sobre el comienzo de la sesión.',
        )
        parser.add_argument(
            '--evento', type=int, default=None,
            help='Limitar a un tipo de evento concreto (su id).',
        )
        parser.add_argument(
            '--incluir-canceladas', action='store_true',
            help='Enviar también las canceladas (llegan con estado «cancelada»).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo contar y listar; no envía nada.',
        )
        parser.add_argument(
            '--sincrono', action='store_true',
            help='Enviar en este proceso en vez de encolar en Celery. Útil para probar contra el LMS.',
        )

    def handle(self, *args, **opts):
        # Sin rango no se envía nada. Ver la nota de arriba: el histórico previo
        # a la integración se queda donde está.
        if not opts['desde']:
            raise CommandError(
                'Falta --desde. Este comando reenvía un rango concreto para tapar '
                'un hueco, no sube el histórico entero.'
            )

        reservas = (
            Reserva.objects
            .filter(event_type__registrar_en_academia=True)
            .select_related('event_type', 'host')
            .order_by('inicio_utc')
        )

        if not opts['incluir_canceladas']:
            reservas = reservas.filter(estado=Reserva.Estado.CONFIRMADA)
        if opts['evento']:
            reservas = reservas.filter(event_type_id=opts['evento'])
        if opts['desde']:
            reservas = reservas.filter(inicio_utc__gte=self._limite(opts['desde']))
        if opts['hasta']:
            reservas = reservas.filter(inicio_utc__lt=self._limite(opts['hasta']))

        total = reservas.count()
        if not total:
            self.stdout.write('No hay reservas que enviar con esos filtros.')
            return

        self.stdout.write(f'{total} reserva(s) a enviar a la academia.')

        if opts['dry_run']:
            for r in reservas.iterator(chunk_size=200):
                self.stdout.write(
                    f'  [{r.pk}] {r.inicio_utc:%Y-%m-%d %H:%M} UTC — '
                    f'{r.host.email} / {r.email_invitado} — {r.estado}'
                )
            self.stdout.write(self.style.WARNING('Dry-run: no se ha enviado nada.'))
            return

        from calendario.bookings.conversions.services import academia
        from calendario.bookings.tasks import process_academia_sesion

        enviadas = fallidas = 0
        for r in reservas.iterator(chunk_size=200):
            if opts['sincrono']:
                # Un fallo no puede tumbar el resto del reenvío: se anota y se
                # sigue, que para eso el envío es idempotente y se puede repetir.
                try:
                    academia.push_sesion(r)
                    enviadas += 1
                except Exception as e:
                    fallidas += 1
                    self.stderr.write(self.style.ERROR(f'  [{r.pk}] {e}'))
            else:
                process_academia_sesion.delay(r.pk)
                enviadas += 1

        modo = 'enviadas' if opts['sincrono'] else 'encoladas'
        self.stdout.write(self.style.SUCCESS(f'{enviadas} {modo}.'))
        if fallidas:
            self.stdout.write(self.style.ERROR(f'{fallidas} con error (arriba el detalle).'))

    def _limite(self, valor):
        try:
            fecha = datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f'Fecha inválida: {valor!r}. Usa YYYY-MM-DD.')
        return datetime.combine(fecha, time.min, tzinfo=dt_timezone.utc)
