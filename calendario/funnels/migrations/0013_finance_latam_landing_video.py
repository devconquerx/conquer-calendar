# -*- coding: utf-8 -*-
"""Añade `landing` y `video` al config del funnel de Conquer Finance (latam).

Réplica del funnel completo de producción (www.conquerfinance.com) en el
calendario: el registro `PropTradingLatam` ya existe (0006 en BDs nuevas, o
sembrado a mano en producción) pero sin `landing` ni `video`, así que su
landing caía a la genérica y el submit saltaba directo al StepForm sin pasar
por la VSL. 0006 es `get_or_create` y NO actualiza registros existentes, por
eso hace falta este parche puntual (mismo patrón que 0008 con Legal).

Cambio MÍNIMO e idempotente: sobre el único registro `key='PropTradingLatam'`
añade exclusivamente `config['landing']` y `config['video']` (leídos del seed
`finance_latam.json`), sin tocar ninguna otra clave del config ni ningún otro
funnel.
"""

import json
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parents[1] / 'seed_data' / 'finance_latam.json'
KEYS = ('landing', 'video')


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    funnel = FunnelForm.objects.filter(key='PropTradingLatam').first()
    if funnel is None:
        return  # BD sin el registro (no debería ocurrir tras 0006): no-op.

    seed = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    seed_cfg = seed.get('config') or {}

    config = funnel.config or {}
    for k in KEYS:
        if k in seed_cfg:
            config[k] = seed_cfg[k]
    funnel.config = config
    funnel.save(update_fields=['config'])


def backwards(apps, schema_editor):
    # No-op: no borramos datos al revertir (igual que 0002–0012).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0012_landing_blocks_eu_us_prod'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
