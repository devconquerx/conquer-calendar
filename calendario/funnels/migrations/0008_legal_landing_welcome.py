# -*- coding: utf-8 -*-
"""Añade `landing` y `welcome` al config del funnel de Conquer Legal (eu).

El registro de conquer-legal ya existe en producción (creado por 0006 en BDs
nuevas, o sembrado a mano antes), pero sin las claves `landing` ni `welcome`,
así que su página de registro no se renderiza. 0006 es `get_or_create` y NO
actualiza registros existentes, por eso hace falta este parche puntual.

Cambio MÍNIMO e idempotente: sobre el único registro `key='LegalEu'` añade
exclusivamente `config['landing']` y `config['welcome']` (leídos del seed
`legal_eu.json`), sin tocar ninguna otra clave del config ni ningún otro
funnel. El valor del vídeo NO vive en el config: está hardcodeado en
`views.py` (`_VIDEO_DEFAULTS`).
"""

import json
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parents[1] / 'seed_data' / 'legal_eu.json'
KEYS = ('landing', 'welcome')


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    funnel = FunnelForm.objects.filter(key='LegalEu').first()
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
    # No-op: no borramos datos al revertir (igual que 0002–0006).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0007_alter_funnelform_slug'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
