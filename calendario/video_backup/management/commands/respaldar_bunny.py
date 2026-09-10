"""Copia el catálogo de Bunny Stream a Cloudflare R2.

Sirve para la carga inicial (`--todo`) y para operar a mano cuando algo se
atasca. El día a día lo lleva la tarea de Celery, que llama al mismo barrido.

    python manage.py respaldar_bunny --dry-run
    python manage.py respaldar_bunny --library 135359 --limite 5
    python manage.py respaldar_bunny --todo
    python manage.py respaldar_bunny --estado
"""

from django.core.management.base import BaseCommand

from calendario.video_backup.models import VideoEspejo
from calendario.video_backup.services import espejo


class Command(BaseCommand):
    help = 'Copia los vídeos de Bunny Stream a Cloudflare R2'

    def add_arguments(self, parser):
        parser.add_argument('--library', help='Copiar sólo esta librería (ID de Bunny).')
        parser.add_argument('--limite', type=int, default=25,
                            help='Máximo de vídeos a copiar en esta ejecución (por defecto 25).')
        parser.add_argument('--todo', action='store_true',
                            help='Sin límite: copia todo lo que falte. Para la carga inicial.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Enseña qué copiaría, sin subir nada.')
        parser.add_argument('--estado', action='store_true',
                            help='Sólo muestra el resumen de lo ya respaldado y sale.')

    def handle(self, *args, **opciones):
        if opciones['estado']:
            self._estado()
            return

        limite = None if opciones['todo'] else opciones['limite']
        resumen = espejo.barrer(
            limite=limite,
            library_id=opciones.get('library'),
            dry_run=opciones['dry_run'],
            log=self.stdout.write,
        )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Revisados {revisados} · copiados {copiados} · ya estaban {ya_estaban} '
            '· omitidos {omitidos} · fallidos {fallidos} · pendientes {pendientes}'.format(**resumen)
        ))
        if resumen['pendientes'] and not opciones['dry_run']:
            self.stdout.write('Quedan vídeos por copiar: vuelve a ejecutar, o usa --todo.')

    def _estado(self):
        filas = VideoEspejo.objects.all()
        copiados = filas.filter(estado=VideoEspejo.COPIADO)
        total_bytes = sum(copiados.values_list('bytes_copiados', flat=True))

        self.stdout.write(f'Filas: {filas.count()}')
        for estado, etiqueta in VideoEspejo.ESTADOS:
            self.stdout.write(f'  {etiqueta}: {filas.filter(estado=estado).count()}')
        self.stdout.write(f'Copiado en R2: {total_bytes / 1e12:.2f} TB')

        borrados = filas.exclude(borrado_en_bunny=None).count()
        if borrados:
            self.stdout.write(f'Ya no están en Bunny (copia conservada): {borrados}')

        fallidos = filas.filter(estado=VideoEspejo.FALLIDO)[:5]
        if fallidos:
            self.stdout.write('')
            self.stdout.write('Últimos fallos:')
            for fila in fallidos:
                self.stdout.write(f'  {fila.library_id}/{fila.guid}: {fila.ultimo_error[:100]}')
