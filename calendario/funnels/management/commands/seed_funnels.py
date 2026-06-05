import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from calendario.event_types.models import EventType
from calendario.funnels.models import FunnelForm, FunnelScoring

# calendario/funnels/management/commands/seed_funnels.py → seed_data está en
# calendario/funnels/seed_data/
SEED_DIR = Path(__file__).resolve().parents[2] / 'seed_data'
SCORING_FILE = SEED_DIR / 'scoring.json'

# Campos del FunnelForm que se persisten desde cada JSON de seed.
FORM_FIELDS = ('slug', 'escuela', 'region', 'nombre', 'config')


class Command(BaseCommand):
    help = (
        'Siembra la tabla de puntuaciones (FunnelScoring) y los formularios '
        'de funnel (FunnelForm) a partir de los JSON en funnels/seed_data/. '
        'Idempotente: la tabla de scoring se actualiza (pk=1) y los '
        'formularios se crean solo si no existen (salvo --force).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--key',
            default=None,
            help='Sembrar solo el FunnelForm con este key (ej. FullLatam).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Actualiza los FunnelForm existentes en vez de saltarlos.',
        )

    def handle(self, *args, **opts):
        if not SEED_DIR.exists():
            raise CommandError(f'No existe el directorio de seed: {SEED_DIR}')

        self._seed_scoring()
        self._seed_forms(key=opts['key'], force=opts['force'])

    def _seed_scoring(self):
        if not SCORING_FILE.exists():
            raise CommandError(f'Falta el archivo de scoring: {SCORING_FILE}')

        config = self._load_json(SCORING_FILE)
        scoring = FunnelScoring.load()
        scoring.config = config
        scoring.save()
        self.stdout.write(self.style.SUCCESS(
            f'FunnelScoring (pk=1) actualizado: {len(config)} campos de puntuación.'
        ))

    def _seed_forms(self, key=None, force=False):
        form_files = sorted(
            f for f in SEED_DIR.glob('*.json') if f.name != 'scoring.json'
        )
        if not form_files:
            self.stdout.write(self.style.WARNING(
                'No hay archivos de formulario en seed_data/ (solo scoring).'
            ))
            return

        sembrados = 0
        for path in form_files:
            data = self._load_json(path)
            form_key = data.get('key')
            if not form_key:
                raise CommandError(f'{path.name}: falta la clave "key".')
            if key and form_key != key:
                continue

            defaults = {f: data[f] for f in FORM_FIELDS if f in data}
            if force:
                obj, created = FunnelForm.objects.update_or_create(
                    key=form_key, defaults=defaults,
                )
                estado = 'creado' if created else 'actualizado'
            else:
                obj, created = FunnelForm.objects.get_or_create(
                    key=form_key, defaults=defaults,
                )
                estado = 'creado' if created else 'ya existía (sin cambios)'

            sembrados += 1
            self.stdout.write(self.style.SUCCESS(
                f"  · FunnelForm '{form_key}' (slug={obj.slug}): {estado}."
            ))
            self._avisar_slugs_evento(form_key, data.get('config', {}))

        if key and sembrados == 0:
            raise CommandError(
                f'No se encontró ningún archivo de seed con key="{key}".'
            )

        self.stdout.write(self.style.SUCCESS(
            f'Formularios procesados: {sembrados}.'
        ))

    def _avisar_slugs_evento(self, form_key, config):
        """Advierte (no falla) si un event_type_slug de los rangos no existe."""
        slugs = [
            r.get('event_type_slug')
            for r in config.get('score_ranges', [])
            if r.get('event_type_slug')
        ]
        if not slugs:
            return
        existentes = set(
            EventType.objects.filter(slug__in=slugs).values_list('slug', flat=True)
        )
        for slug in slugs:
            if slug not in existentes:
                self.stdout.write(self.style.WARNING(
                    f"    ⚠ {form_key}: event_type_slug '{slug}' no existe aún en la BD "
                    f"(Alexis debe crear el EventType o ajustar el rango en el admin)."
                ))

    @staticmethod
    def _load_json(path):
        try:
            with path.open(encoding='utf-8') as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            raise CommandError(f'JSON inválido en {path.name}: {exc}') from exc
