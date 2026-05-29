from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

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

        ok = 0
        for host in hosts:
            self.stdout.write(f"  → {host.email} ... ", ending='')
            sincronizar_host_completo(host)

            from calendario.google_calendar.models import GoogleCalendarSyncEstado
            try:
                sync_estado = GoogleCalendarSyncEstado.objects.get(host=host)
                if sync_estado.estado == GoogleCalendarSyncEstado.ACTIVO:
                    from calendario.google_calendar.models import GoogleCalendarEvento
                    n = GoogleCalendarEvento.objects.filter(host=host).count()
                    self.stdout.write(self.style.SUCCESS(f"OK ({n} eventos)"))
                    ok += 1
                else:
                    self.stdout.write(self.style.ERROR(f"ERROR (ver logs)"))
            except GoogleCalendarSyncEstado.DoesNotExist:
                self.stdout.write(self.style.ERROR("ERROR (sin sync_estado)"))

        self.stdout.write(f"\nCompletado: {ok}/{total} hosts sincronizados correctamente.")
