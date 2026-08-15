# -*- coding: utf-8 -*-
"""Corrige la primera opción de `income_target` en Conquer Blocks EU.

Estaba con el texto en dólares de LATAM ("...2000 dólares americanos al
mes.") en vez del propio de EU en euros ("...3000 euros al mes."), verificado
contra `conquerx-funnels-new/output.json` (formFullStackEu). Ambos textos
puntúan 4 en la tabla de scoring (`scoring.json`), así que el bug era solo de
copy — no afectaba el resultado del quiz —, pero el texto mostrado al lead
era el equivocado.

Blocks EU ya está desplegado en producción con `get_or_create` (0006), así
que corregir el JSON de `seed_data/` no llega a la fila existente — hay que
parchearla aquí, igual que 0003/0012/0019.
"""
from django.db import migrations

OLD_LABEL = 'Tener un salario de más de 2000 dólares americanos al mes.'
NEW_LABEL = 'Tener un salario de más de 3000 euros al mes.'


def _patch(apps, old_label, new_label):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    ff = FunnelForm.objects.filter(key='FullEu').first()
    if not ff:
        return
    cfg = ff.config or {}
    changed = False
    for block in cfg.get('blocks', []):
        if block.get('id') != 'income_target':
            continue
        for choice in block.get('attributes', {}).get('choices', []):
            if choice.get('value') == old_label:
                choice['label'] = new_label
                choice['value'] = new_label
                changed = True
    if changed:
        ff.config = cfg
        ff.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _patch(apps, OLD_LABEL, NEW_LABEL)


def backwards(apps, schema_editor):
    _patch(apps, NEW_LABEL, OLD_LABEL)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0019_blocks_us_calendlys_for_cancelled'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
