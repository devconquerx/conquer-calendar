"""Inyecta la `calendly_url` de producción en cada rango de score por funnel.

Fuente de verdad: `conquerx-funnels-new/output.json` (sistema en producción),
donde cada funnel mapea su score a una URL de Calendly. Aquí replicamos ese
mapeo por `key` del FunnelForm, asignando una URL por rango (en orden).

Idempotente: solo escribe `calendly_url` si el funnel existe y el número de
rangos coincide con el de URLs. No toca `event_type_slug` (modo calendario
local, aún no usado). Marcas sin Calendly en output.json (EnglishKids*, Legal*)
se omiten a propósito.
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


def set_calendly_urls(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for key, urls in CALENDLY_POR_KEY.items():
        funnel = FunnelForm.objects.filter(key=key).first()
        if not funnel:
            continue
        config = funnel.config or {}
        ranges = config.get('score_ranges') or []
        if len(ranges) != len(urls):
            # Estructura inesperada: no arriesgamos un mapeo cruzado.
            continue
        for rango, url in zip(ranges, urls):
            rango['calendly_url'] = url
        config['score_ranges'] = ranges
        funnel.config = config
        funnel.save(update_fields=['config'])


def unset_calendly_urls(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for key in CALENDLY_POR_KEY:
        funnel = FunnelForm.objects.filter(key=key).first()
        if not funnel:
            continue
        config = funnel.config or {}
        for rango in config.get('score_ranges') or []:
            rango.pop('calendly_url', None)
        funnel.config = config
        funnel.save(update_fields=['config'])


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0004_funnel_video_config'),
    ]

    operations = [
        migrations.RunPython(set_calendly_urls, unset_calendly_urls),
    ]
