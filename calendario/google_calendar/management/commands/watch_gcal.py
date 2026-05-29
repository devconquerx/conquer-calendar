from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from calendario.google_calendar.sync import registrar_canal_watch

User = get_user_model()


class Command(BaseCommand):
    help = 'Registra canales push de Google Calendar (events.watch) para hosts.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--host', type=str, help='Email del host')
        group.add_argument('--todos', action='store_true', help='Registrar canal para todos los usuarios activos')

    def handle(self, *args, **options):
        webhook_url = getattr(settings, 'GCAL_WEBHOOK_URL', '')
        if not webhook_url:
            raise CommandError(
                'GCAL_WEBHOOK_URL no está configurada en settings. '
                'Define la URL pública del receptor de webhooks (p.ej. https://tudominio.com/webhooks/google-calendar/).'
            )

        if options['host']:
            try:
                host = User.objects.get(email=options['host'], is_active=True)
            except User.DoesNotExist:
                raise CommandError(f"No existe ningún usuario activo con email '{options['host']}'")
            hosts = [host]
        else:
            hosts = list(User.objects.filter(is_active=True))

        total = len(hosts)
        self.stdout.write(f"Registrando canales watch para {total} host(s) → {webhook_url}")

        ok = 0
        for host in hosts:
            self.stdout.write(f"  → {host.email} ... ", ending='')
            exito = registrar_canal_watch(host, webhook_url)
            if exito:
                self.stdout.write(self.style.SUCCESS("OK"))
                ok += 1
            else:
                self.stdout.write(self.style.ERROR("ERROR (ver logs)"))

        self.stdout.write(f"\nCompletado: {ok}/{total} canales registrados.")
