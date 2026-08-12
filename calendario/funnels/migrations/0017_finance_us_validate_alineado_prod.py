# -*- coding: utf-8 -*-
"""Vacía `config['validate']` de Conquer Finance US para alinear con producción.

En `conquerx-funnels-new/src/data/formObj.jsx`, `formPropTradingUs` se
construye con `createBaseForm(..., CALENDLY_CONFIGS.financeUs)` — sin pasar
el argumento `validate`, que por defecto queda en `[]`. Existe una
`VALIDATION_RULES.financeUs` definida en ese archivo (edad + "Ahorro menos de
75 dólares al mes") pero JAMÁS se referencia en la llamada: es código muerto.
En producción real, ningún lead US se rechaza por respuestas — solo por
`score_ranges` (0–100, cubre a todos).

El seed `finance_us.json` sí traía una regla (`age: 'Soy menor de 18 años.'`),
así que un lead US menor de edad quedaba rechazado (`motivo='validate'` en
`scoring.resolver_outcome`) cuando en producción pasa al calendario sin
problema. Verificado 2026-08-12 comparando ambos repos.

Cambio MÍNIMO e idempotente: sobre el único registro `key='PropTradingUs'`
vacía exclusivamente `config['validate']`, sin tocar ninguna otra clave del
config ni ningún otro funnel.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    funnel = FunnelForm.objects.filter(key='PropTradingUs').first()
    if funnel is None:
        return  # BD sin el registro: no-op.

    config = funnel.config or {}
    if config.get('validate'):
        config['validate'] = []
        funnel.config = config
        funnel.save(update_fields=['config'])


def backwards(apps, schema_editor):
    # No-op: no restauramos la regla al revertir (igual que 0002–0016).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0016_finance_eu_landing_video'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
