# -*- coding: utf-8 -*-
"""Da a cada región de Conquer Blocks su propio vídeo (bug real encontrado).

LATAM/EU/US no traían `config.video` propio, así que las 3 caían al fallback
compartido `_VIDEO_DEFAULTS['conquer-blocks']` (views.py) — el vídeo de EU
("conquerblocks-spain..."). LATAM y US mostraban el vídeo equivocado; EU
coincidía por pura casualidad (el fallback ES el vídeo de EU).

URLs reales por región, de `conquerx-funnels-new/src/utils/cb-video-page.js`
(dataCb): mismas que ya usa `blocks_eu_2.json` en su propio `config.video`.
"""
from django.db import migrations

VIDEO_POR_KEY = {
    'FullLatam': ['https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-latam-2025.mp4'],
    'FullEu': ['https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain-2025-compress.mp4'],
    'FullUs': ['https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-usa.mp4'],
}


def _patch(apps, set_video):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for key, urls in VIDEO_POR_KEY.items():
        ff = FunnelForm.objects.filter(key=key).first()
        if not ff:
            continue
        cfg = ff.config or {}
        if set_video:
            cfg['video'] = {'videoUrls': urls, 'buttonPercent': 75}
        else:
            cfg.pop('video', None)
        ff.config = cfg
        ff.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _patch(apps, True)


def backwards(apps, schema_editor):
    _patch(apps, False)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0021_seed_blocks_eu_2'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
