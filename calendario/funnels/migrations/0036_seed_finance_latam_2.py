# -*- coding: utf-8 -*-
"""Crea la segunda landing LATAM de Conquer Finance (finance-latam-2, fi-latam-2).

Marketing pide para LATAM (25-sep-2026) lo mismo que la LP2 de EU (0035),
con la misma copy. Por eso se combinan dos filas:

  - la BASE es finance-latam tal como esté en cada BD: quiz, scoring,
    textos del StepForm, vídeo y los `score_ranges` con los EventTypes LATAM
    de ESE entorno (sus ids difieren entre local y producción);
  - el LANDING se toma entero de finance-eu-2 (copy, teléfono obligatorio,
    textos del formulario y línea de contacto propia), así las dos LP2 salen
    idénticas sin duplicar la copy aquí.

El vídeo es de momento el VSL de finance-latam; cuando llegue el de la LP2 se
cambia en `config.video` desde el admin.

Idempotente: `get_or_create` por `key` → no pisa ediciones hechas después en
el admin.
"""
import copy

from django.db import migrations


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    if FunnelForm.objects.filter(key='PropTradingLatam2').exists():
        return
    latam = FunnelForm.objects.filter(slug='finance-latam').first()
    eu_2 = FunnelForm.objects.filter(slug='finance-eu-2').first()
    if latam is None or eu_2 is None:
        return
    config = copy.deepcopy(latam.config or {})
    config['key'] = 'PropTradingLatam2'
    config['landing'] = copy.deepcopy((eu_2.config or {}).get('landing') or {})
    FunnelForm.objects.create(
        key='PropTradingLatam2',
        slug='finance-latam-2',
        escuela=latam.escuela,
        region=latam.region,
        nombre='Conquer Finance — LATAM 2 (LP2)',
        config=config,
        activo=True,
    )


def backwards(apps, schema_editor):
    # No-op: no borramos datos sembrados al revertir (igual que 0006/0035).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0035_seed_finance_eu_2'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
