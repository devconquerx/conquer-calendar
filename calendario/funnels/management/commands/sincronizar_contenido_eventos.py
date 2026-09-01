# -*- coding: utf-8 -*-
"""Crea la fila de textos de las páginas de evento que aún no la tengan.

La migración creó una por cada página que había al montar esto. Cuando se añada
una página nueva a `contenido.PAGINAS`, este comando le crea la suya para que
salga en el admin:

    python manage.py sincronizar_contenido_eventos

Nace vacía, así que la página sigue sirviendo los textos del código hasta que
alguien la edite. No borra nada: si se quita una página del registro, su fila se
queda ahí con lo que tuviera escrito.
"""
from django.core.management.base import BaseCommand

from calendario.funnels.contenido import PAGINAS
from calendario.funnels.models import ContenidoDeEvento


class Command(BaseCommand):
    help = 'Crea la fila de textos de las páginas de evento que no la tengan.'

    def handle(self, *args, **opciones):
        creadas = []
        for clave in PAGINAS:
            _, creada = ContenidoDeEvento.objects.get_or_create(clave=clave, defaults={'textos': {}})
            if creada:
                creadas.append(clave)
        if creadas:
            self.stdout.write(self.style.SUCCESS(
                f'Creadas {len(creadas)}: ' + ', '.join(creadas)))
        else:
            self.stdout.write('Todas las páginas ya tenían su fila.')
