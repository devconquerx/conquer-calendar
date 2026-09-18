# -*- coding: utf-8 -*-
"""La fila de textos de la bitácora de la Coding Week.

Nace vacía, como el resto (ver 0028): mientras nadie edite nada, la página
sirve los textos con los que se migró desde Webflow. La fila hace falta igual,
porque el editor del panel la busca por clave.
"""
from django.db import migrations


CLAVE = 'bitacora-coding-week'


def crear_fila(apps, schema_editor):
    ContenidoDeEvento = apps.get_model('funnels', 'ContenidoDeEvento')
    ContenidoDeEvento.objects.get_or_create(clave=CLAVE, defaults={'textos': {}})


def borrar_fila(apps, schema_editor):
    ContenidoDeEvento = apps.get_model('funnels', 'ContenidoDeEvento')
    ContenidoDeEvento.objects.filter(clave=CLAVE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0033_blocks_eu_2_landing_propio'),
    ]

    operations = [
        migrations.RunPython(crear_fila, borrar_fila),
    ]
