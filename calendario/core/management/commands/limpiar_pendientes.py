"""Borra las marcas de "pendiente" de calendario/core/resiliencia.py.

check_colas ya limpia sola cada minuto las huérfanas (las que apuntan a un
mensaje que no está en el broker). Esto es para hacerlo al momento tras purgar
una cola a mano, o para borrarlas todas (--todas) si hiciera falta.
"""
from django.core.management.base import BaseCommand

from calendario.core import resiliencia


class Command(BaseCommand):
    help = 'Borra las marcas de pendiente huérfanas (o todas con --todas).'

    def add_arguments(self, parser):
        parser.add_argument('--todas', action='store_true',
                            help='Borra todas, no solo las huérfanas. El sweep reencolará lo que falte.')

    def handle(self, *args, **opts):
        n = resiliencia.limpiar_pendientes_huerfanas(gracia=0, todas=opts['todas'])
        self.stdout.write(self.style.SUCCESS(f'{n} marcas de pendiente borradas'))
