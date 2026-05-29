from django.core.management.base import BaseCommand

from calendario.google_calendar.sync import renovar_canales_por_expirar


class Command(BaseCommand):
    help = (
        'Renueva los canales push de Google Calendar cuya expiración está próxima. '
        'Lanzar por cron diariamente.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--margen-horas',
            type=int,
            default=24,
            help='Renovar canales que expiran en menos de N horas (default: 24)',
        )

    def handle(self, *args, **options):
        margen = options['margen_horas']
        self.stdout.write(f"Renovando canales con expiración en menos de {margen}h...")
        renovar_canales_por_expirar(margen_horas=margen)
        self.stdout.write(self.style.SUCCESS("Completado."))
