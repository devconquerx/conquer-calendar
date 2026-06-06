# -*- coding: utf-8 -*-
# Añade la config de la página de video (videoUrls + buttonPercent) a los
# funnels de conquer-blocks. Idempotente: solo escribe si falta config['video'].
from django.db import migrations

VIDEO_URLS = [
    'https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain-2025-compress.mp4',
    'https://vslconquerx.b-cdn.net/conquerblocks/conquerblocks-spain.mp4',
]
BUTTON_PERCENT = 75


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for ff in FunnelForm.objects.filter(escuela='conquer-blocks'):
        cfg = ff.config or {}
        if cfg.get('video'):
            continue
        cfg['video'] = {'videoUrls': VIDEO_URLS, 'buttonPercent': BUTTON_PERCENT}
        ff.config = cfg
        ff.save(update_fields=['config'])


def backwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for ff in FunnelForm.objects.filter(escuela='conquer-blocks'):
        cfg = ff.config or {}
        if 'video' in cfg:
            del cfg['video']
            ff.config = cfg
            ff.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0003_landing_blocks_latam_prod'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
