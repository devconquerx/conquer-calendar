# -*- coding: utf-8 -*-
"""Añade `landing` y `video` al config del funnel de Conquer Finance (us).

Mismo caso que 0013 con LATAM: el registro `PropTradingUs` ya existe (seed +
0014 le rellenó calendly_url) pero sin `landing` ni `video`, así que su
landing caía a la genérica y el submit saltaba directo al StepForm sin pasar
por la VSL.

Contenido verificado 1:1 contra producción (conquerfinance.com/clase-online-
gratuita-us y /video-clase-us, jul 2026): la landing y el copy del vídeo son
IDÉNTICOS a los de LATAM (mismo H1, bullets, disclaimer y bio de Félix); lo
único que cambia es el archivo del VSL, que en US es un vídeo distinto
(`vsl-cf-2025-compress.mp4`, no el de LATAM).

Cambio MÍNIMO e idempotente: sobre el único registro `key='PropTradingUs'`
añade exclusivamente `config['landing']` y `config['video']` (leídos del seed
`finance_us.json`), sin tocar ninguna otra clave del config ni ningún otro
funnel.
"""

import json
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parents[1] / 'seed_data' / 'finance_us.json'
KEYS = ('landing', 'video')


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    funnel = FunnelForm.objects.filter(key='PropTradingUs').first()
    if funnel is None:
        return  # BD sin el registro: no-op.

    seed = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    seed_cfg = seed.get('config') or {}

    config = funnel.config or {}
    for k in KEYS:
        if k in seed_cfg:
            config[k] = seed_cfg[k]
    funnel.config = config
    funnel.save(update_fields=['config'])


def backwards(apps, schema_editor):
    # No-op: no borramos datos al revertir (igual que 0002–0013).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0014_backfill_calendly_urls'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
