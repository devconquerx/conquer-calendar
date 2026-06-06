# -*- coding: utf-8 -*-
"""Siembra inicial de los FunnelForm + FunnelScoring desde funnels/seed_data/.

Hasta ahora los registros se creaban con el comando manual `seed_funnels`, y
las migraciones 0002–0005 solo *parcheaban* registros existentes. En una BD
fresca (p.ej. producción) esas migraciones corren sobre tablas vacías y no
crean nada, dejando el funnel sin datos. Esta migración cierra ese hueco:
crea los registros de forma idempotente al aplicar `migrate`, que ya forma
parte del deploy.

Idempotente: `get_or_create` por `key`/`pk` → no duplica ni pisa ediciones
hechas en el admin o por `seed_funnels --force`. En entornos ya sembrados
(dev/local) es un no-op. El JSON de `seed_data/` sigue siendo la fuente
editable; este alta inicial lee de ahí. Para re-sembrar tras editar el JSON,
usar `python manage.py seed_funnels --force`.
"""

import json
from pathlib import Path

from django.db import migrations

SEED_DIR = Path(__file__).resolve().parents[1] / 'seed_data'
SCORING_FILE = SEED_DIR / 'scoring.json'

# Campos del FunnelForm que se persisten desde cada JSON (igual que el comando
# seed_funnels: el resto del contenido vive dentro de `config`).
FORM_FIELDS = ('slug', 'escuela', 'region', 'nombre', 'config')


def _load(path):
    with path.open(encoding='utf-8') as fh:
        return json.load(fh)


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    FunnelScoring = apps.get_model('funnels', 'FunnelScoring')

    # Tabla de puntuaciones (singleton pk=1).
    if SCORING_FILE.exists():
        FunnelScoring.objects.get_or_create(
            pk=1, defaults={'config': _load(SCORING_FILE)},
        )

    # Un FunnelForm por archivo de seed (excepto scoring.json).
    for path in sorted(SEED_DIR.glob('*.json')):
        if path.name == 'scoring.json':
            continue
        data = _load(path)
        key = data.get('key')
        if not key:
            continue
        defaults = {f: data[f] for f in FORM_FIELDS if f in data}
        FunnelForm.objects.get_or_create(key=key, defaults=defaults)


def backwards(apps, schema_editor):
    # No-op: no borramos datos sembrados al revertir (igual que 0002–0005).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0005_score_ranges_calendly_url'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
