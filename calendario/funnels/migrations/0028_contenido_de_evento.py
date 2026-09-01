# -*- coding: utf-8 -*-
"""La tabla de textos de las páginas de evento, con su fila por página.

Las filas nacen vacías a propósito: mientras nadie edite nada, cada página sirve
los textos con los que se migró desde Webflow (los de las fichas de
`evento_views`). La primera vez que se guarda una página desde el admin, sus
textos pasan a la BD y desde entonces mandan estos.
"""
from django.db import migrations, models


# Las páginas conocidas, en el orden de la tabla de /funnels/. Va escrito aquí y
# no importado de `contenido.PAGINAS` porque una migración tiene que seguir
# corriendo igual dentro de un año, con el registro cambiado.
PAGINAS = [
    'lanzamiento-blocks',
    'lanzamiento-finance',
    'lanzamiento-languages',
    'gracias-blocks',
    'gracias-finance',
    'gracias-languages',
    'gracias-trading-week',
    'coding-week',
    'testimonios',
    'bitacora',
    'pildora-1',
    'pildora-2',
    'pildora-3',
    'trading-week',
]


def crear_filas(apps, schema_editor):
    ContenidoDeEvento = apps.get_model('funnels', 'ContenidoDeEvento')
    for clave in PAGINAS:
        ContenidoDeEvento.objects.get_or_create(clave=clave, defaults={'textos': {}})


def borrar_filas(apps, schema_editor):
    ContenidoDeEvento = apps.get_model('funnels', 'ContenidoDeEvento')
    ContenidoDeEvento.objects.filter(clave__in=PAGINAS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0027_blocks_eu_checkbox_whatsapp_fijo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContenidoDeEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('clave', models.SlugField(
                    help_text='Identificador de la página en `contenido.PAGINAS`.',
                    max_length=60, unique=True, verbose_name='Página')),
                ('textos', models.JSONField(
                    blank=True, default=dict,
                    help_text='{clave: valor} de los textos editados. Lo que falte sale del código.',
                    verbose_name='Textos')),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'textos de una página de evento',
                'verbose_name_plural': 'textos de las páginas de evento',
                'db_table': 'contenido_eventos',
                'ordering': ['clave'],
            },
        ),
        migrations.RunPython(crear_filas, borrar_filas),
    ]
