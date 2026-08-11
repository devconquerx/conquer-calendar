# -*- coding: utf-8 -*-
"""Añade `landing` y `video` al config del funnel de Conquer Finance (eu).

Mismo caso que 0013 (LATAM) y 0015 (US): el registro `PropTradingEu` ya existe
(seed + 0014 le rellenó calendly_url) pero sin `landing` ni `video`.

A diferencia de LATAM/US, la landing REAL de EU no es la landing "teaser" que
comparten esas dos regiones — es la copy "resultados" (verificada 1:1 contra
producción, jul/ago 2026, en conquerfinance.com/clase-online-gratuita-eu):
mismo título/bullets que el bloque `welcome` de LATAM, más 3 párrafos de
disclaimer (LATAM/US solo tienen uno). El vídeo (`/video-clase-eu`) sí
comparte título/subtítulo genéricos con LATAM/US; el archivo del VSL es el
mismo que US (`vsl-cf-2025-compress.mp4`, distinto del de LATAM).

Cambio MÍNIMO e idempotente: sobre el único registro `key='PropTradingEu'`
añade exclusivamente `config['landing']` y `config['video']` (leídos del seed
`finance_eu.json`), sin tocar ninguna otra clave del config ni ningún otro
funnel.
"""

import json
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parents[1] / 'seed_data' / 'finance_eu.json'
KEYS = ('landing', 'video')


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    funnel = FunnelForm.objects.filter(key='PropTradingEu').first()
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
    # No-op: no borramos datos al revertir (igual que 0002–0015).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0015_finance_us_landing_video'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
