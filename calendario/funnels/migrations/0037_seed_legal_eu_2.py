# -*- coding: utf-8 -*-
"""Crea la segunda landing EU de Conquer Legal (legal-eu-2, cg-eu-2).

Pedida el 12-oct-2026 en conquerlegal.com/hub/registro-2-eu y /hub/video-2-eu.
Registro y prellamada propios (su StepForm va en /hub/agendar-2-eu), pero la
reserva es la misma que la de legal-eu: los `score_ranges` apuntan a sus
mismos EventTypes.

Se clona la fila de legal-eu TAL COMO ESTÉ en cada BD en vez de sembrar un
JSON: así hereda la landing, el quiz, el scoring, el vídeo y los `score_ranges`
con los EventTypes de ESE entorno, cuyos ids difieren entre local y producción.
De momento es una copia exacta; el vídeo propio se cambia luego en
`config.video` desde el admin.

Idempotente: no hace nada si ya existe la key → no pisa ediciones hechas
después en el admin.
"""
import copy

from django.db import migrations


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    if FunnelForm.objects.filter(key='LegalEu2').exists():
        return
    eu = FunnelForm.objects.filter(slug='legal-eu').first()
    if eu is None:
        return
    config = copy.deepcopy(eu.config or {})
    config['key'] = 'LegalEu2'
    FunnelForm.objects.create(
        key='LegalEu2',
        slug='legal-eu-2',
        escuela=eu.escuela,
        region=eu.region,
        nombre='Conquer Legal — EU 2',
        config=config,
        activo=True,
    )


def backwards(apps, schema_editor):
    # No-op: no borramos datos sembrados al revertir (igual que 0035/0036).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0036_seed_finance_latam_2'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
