from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from calendario.google_calendar.models import (
    GoogleCalendarEvento,
    GoogleCalendarSyncEstado,
    GoogleCalendarSyncLog,
)
from calendario.google_calendar.sync import sincronizar_host_completo

User = get_user_model()


class Command(BaseCommand):
    help = 'Sync inicial completo de eventos de Google Calendar para uno o todos los hosts.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--host', type=str, help='Email del host a sincronizar')
        group.add_argument('--todos', action='store_true', help='Sincronizar todos los usuarios activos')

    def handle(self, *args, **options):
        if options['host']:
            try:
                host = User.objects.get(email=options['host'], is_active=True)
            except User.DoesNotExist:
                raise CommandError(f"No existe ningún usuario activo con email '{options['host']}'")
            hosts = [host]
        else:
            hosts = list(User.objects.filter(is_active=True))

        total = len(hosts)
        self.stdout.write(f"Iniciando sync completo para {total} host(s)...")

        exitosos = 0
        fallidos_emails = []
        for host in hosts:
            self.stdout.write(f"  → {host.email} ... ", ending='')
            sincronizar_host_completo(host)

            try:
                sync_estado = GoogleCalendarSyncEstado.objects.get(host=host)
                if sync_estado.estado == GoogleCalendarSyncEstado.ACTIVO:
                    n = GoogleCalendarEvento.objects.filter(host=host).count()
                    self.stdout.write(self.style.SUCCESS(f"OK ({n} eventos)"))
                    exitosos += 1
                else:
                    self.stdout.write(self.style.ERROR("ERROR (ver logs)"))
                    fallidos_emails.append(host.email)
            except GoogleCalendarSyncEstado.DoesNotExist:
                self.stdout.write(self.style.ERROR("ERROR (sin sync_estado)"))
                fallidos_emails.append(host.email)

        self.stdout.write(f"\nCompletado: {exitosos}/{total} hosts sincronizados correctamente.")
        GoogleCalendarSyncLog.registrar(
            GoogleCalendarSyncLog.SYNC_INICIAL, total, exitosos, fallidos_emails
        )
