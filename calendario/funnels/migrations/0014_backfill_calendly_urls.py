# -*- coding: utf-8 -*-
"""Rellena las `calendly_url` de los score_ranges que quedaron vacías.

La 0005 inyectaba las URLs de Calendly de producción por `key`, pero está
ANTES de la 0006 (que es la que crea los FunnelForm con `get_or_create`): en
cualquier BD donde los funnels no existieran ya al aplicar 0005 —BDs locales
frescas y también producción, verificado el 2026-07-27 con PropTradingLatam—
la 0005 fue un no-op y los rangos quedaron sin destino, con lo que el resolver
rechaza todo con motivo `sin_destino`.

Misma tabla key→URLs que la 0005 (fuente: conquerx-funnels-new/output.json,
el sistema en producción). Idempotente y conservador: solo escribe
`calendly_url` donde falte o esté vacía, solo si el número de rangos coincide
con el de URLs, y no toca ninguna otra clave (ni `event_type_*`, que es el
modo calendario local de Legal).
"""
from django.db import migrations

# key del FunnelForm → lista de URLs de Calendly, una por rango (en orden).
CALENDLY_POR_KEY = {
    'FullLatam': [
        'https://calendly.com/d/cqy7-kcx-jmc/sesion-de-consultoria-conquer-blocks-latam',
        'https://calendly.com/d/cnh3-q3p-mw5/sesion-de-consultoria-conquer-blocks-latam',
    ],
    'FullEu': [
        'https://calendly.com/d/cm8m-fpp-7sc/sesion-de-consultoria-conquer-blocks-eu',
        'https://calendly.com/d/cqv6-8dc-tyr/sesion-de-consultoria-conquer-blocks-eu',
    ],
    'FullUs': [
        'https://calendly.com/d/crft-6hj-zmm/sesion-de-consultoria-conquer-blocks-us',
    ],
    'EspLatam': [
        'https://calendly.com/d/cwqp-6p4-b48/especialidad-sesion-conquer-blocks-latam',
    ],
    'EspEu': [
        'https://calendly.com/d/cwqr-smg-tbd/especialidad-sesion-de-consultoria-conquer-blocks-eu',
    ],
    'EspUs': [
        'https://calendly.com/d/cszj-pcd-cjn/especialidad-sesion-conquer-blocks-usa',
    ],
    'PropTradingLatam': [
        'https://calendly.com/d/cq57-xx7-2kf/sesion-de-consultoria-conquer-finance-latam',
        'https://calendly.com/d/3p4-8yy-cdm/sesion-de-consultoria-conquer-finance-latam',
    ],
    'PropTradingEu': [
        'https://calendly.com/d/cnt6-mc9-ffy/sesion-de-consultoria-conquer-finance-eu',
        'https://calendly.com/d/ck24-gd9-f2z/sesion-de-consultoria-conquer-finance-eu',
    ],
    'PropTradingUs': [
        'https://calendly.com/d/3q2-8bx-c98/sesion-de-consultoria-conquer-finance-us',
    ],
    'EnglishLatam': [
        'https://calendly.com/d/cny6-z8m-gy7/sesion-de-consultoria-conquer-languages-latam',
        'https://calendly.com/d/cqpw-xd6-x4b/sesion-de-consultoria-conquer-languages-latam',
    ],
    'EnglishEu': [
        'https://calendly.com/d/crf7-dtd-7gd/sesion-de-consultoria-conquer-languages-eu',
        'https://calendly.com/d/cmyh-qnj-z8x/sesion-de-consultoria-conquer-languages-eu',
    ],
    'EnglishUs': [
        'https://calendly.com/d/cqp7-z7c-bg4/sesion-de-consultoria-conquer-languages-us',
    ],
}


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for key, urls in CALENDLY_POR_KEY.items():
        funnel = FunnelForm.objects.filter(key=key).first()
        if funnel is None:
            continue
        config = funnel.config or {}
        ranges = config.get('score_ranges') or []
        if len(ranges) != len(urls):
            continue
        cambiado = False
        for rango, url in zip(ranges, urls):
            if not rango.get('calendly_url'):
                rango['calendly_url'] = url
                cambiado = True
        if cambiado:
            config['score_ranges'] = ranges
            funnel.config = config
            funnel.save(update_fields=['config'])


def backwards(apps, schema_editor):
    # No-op: no borramos datos al revertir (igual que 0002–0013).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0013_finance_latam_landing_video'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
