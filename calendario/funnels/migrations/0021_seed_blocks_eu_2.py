# -*- coding: utf-8 -*-
"""Crea el FunnelForm de la segunda landing EU de Conquer Blocks (blocks-eu-2).

Réplica de `cb-eu-2` de conquerx-funnels-new (ruta
`/conquer-blocks/clase-2-online-gratuita-eu`, funnel `cb-eu-2`, A/B propio
`form_variant_cb_eu_2` 53/54 y vídeo corto), que comparte escuela+región con
`blocks-eu` pero es una landing (y config) propia — contenido capturado en
vivo de www.conquerblocks.com/conquer-blocks/clase-2-online-gratuita-eu.

Blocks ya está desplegado en producción, así que — a diferencia de
`blocks_latam.json`/`blocks_eu.json`/`blocks_us.json`, que si son nuevos en
una BD entran solos por el glob de 0006 — esta fila necesita alta explícita
aquí para que llegue a la BD ya migrada. El JSON de `seed_data/` sigue siendo
la fuente editable (y también sirve para altas en BDs frescas vía el glob de
0006, que lo recogerá automáticamente al no existir aún la clave `FullEu2`).

Idempotente: `get_or_create` por `key` → no pisa ediciones hechas en el admin
o por `seed_funnels --force`.
"""
import json
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parents[1] / 'seed_data' / 'blocks_eu_2.json'

FORM_FIELDS = ('slug', 'escuela', 'region', 'nombre', 'config')


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    if not SEED_FILE.exists():
        return
    with SEED_FILE.open(encoding='utf-8') as fh:
        data = json.load(fh)
    key = data.get('key')
    if not key:
        return
    defaults = {f: data[f] for f in FORM_FIELDS if f in data}
    FunnelForm.objects.get_or_create(key=key, defaults=defaults)


def backwards(apps, schema_editor):
    # No-op: no borramos datos sembrados al revertir (igual que 0006).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0020_blocks_eu_income_target_currency'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
