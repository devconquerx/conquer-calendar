from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from calendario.google_calendar.models import GoogleCalendarSyncEstado, GoogleCalendarSyncLog
from calendario.google_calendar.sync import sincronizar_host_incremental

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Sync incremental de eventos de Google Calendar usando syncToken. '
        'Lanzar por cron cada 10-15 min como red de seguridad.'
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--host', type=str, help='Email del host a sincronizar')
        group.add_argument('--todos', action='store_true', help='Sincronizar todos los hosts con sync activo')

    def handle(self, *args, **options):
        if options['host']:
            try:
                host = User.objects.get(email=options['host'], is_active=True)
            except User.DoesNotExist:
                raise CommandError(f"No existe ningún usuario activo con email '{options['host']}'")
            hosts = [host]
        else:
            host_ids = (
                GoogleCalendarSyncEstado.objects
                .filter(estado__in=[GoogleCalendarSyncEstado.ACTIVO, GoogleCalendarSyncEstado.ERROR])
                .values_list('host_id', flat=True)
            )
            hosts = list(User.objects.filter(id__in=host_ids, is_active=True))

        total = len(hosts)
        if total == 0:
            self.stdout.write("No hay hosts con sync inicializado.")
            return

        self.stdout.write(f"Sync incremental para {total} host(s)...")

        exitosos = 0
        fallidos_emails = []
        for host in hosts:
            self.stdout.write(f"  → {host.email} ... ", ending='')
            sincronizar_host_incremental(host)
            try:
                sync = GoogleCalendarSyncEstado.objects.get(host=host)
                if sync.estado == GoogleCalendarSyncEstado.ACTIVO:
                    self.stdout.write(self.style.SUCCESS("OK"))
                    exitosos += 1
                else:
                    self.stdout.write(self.style.ERROR(f"ERROR (estado={sync.estado})"))
                    fallidos_emails.append(host.email)
            except GoogleCalendarSyncEstado.DoesNotExist:
                self.stdout.write(self.style.WARNING("sin estado"))
                fallidos_emails.append(host.email)

        self.stdout.write("Completado.")
        GoogleCalendarSyncLog.registrar(
            GoogleCalendarSyncLog.SYNC_INCREMENTAL, total, exitosos, fallidos_emails
        )
