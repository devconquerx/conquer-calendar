# -*- coding: utf-8 -*-
"""Alinea Conquer Blocks US con la pantalla de precio del funnel viejo.

En conquerx-funnels-new, `formFullStackUs.calendlys_for_cancelled` (única
región/marca con esta clave) hace que un lead descalificado por `validate`
(o, si aplicara, por score bajo) NO vea el rechazo directo: en su lugar ve una
pantalla de transparencia de precio ("a partir de 3.500 dólares...") con un
botón para agendar igual, que abre este mismo Calendly.

Blocks US ya estaba desplegado en producción con `get_or_create` (0006), así
que añadir la clave al JSON de `seed_data/` no llega a la fila existente —
hay que parchearla aquí, igual que 0003/0012 con el contenido de landing.
"""
from django.db import migrations

CALENDLYS_FOR_CANCELLED = {
    'url': 'https://calendly.com/d/cvny-mq6-gd7/sesion-de-consultoria-conquer-blocks-usa',
    'price': '3,500 dólares',
}


def _patch(apps, value):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    ff = FunnelForm.objects.filter(key='FullUs').first()
    if not ff:
        return
    cfg = ff.config or {}
    if value is None:
        cfg.pop('calendlys_for_cancelled', None)
    else:
        cfg['calendlys_for_cancelled'] = value
    ff.config = cfg
    ff.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _patch(apps, CALENDLYS_FOR_CANCELLED)


def backwards(apps, schema_editor):
    _patch(apps, None)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0018_finance_latam_un_solo_event_type'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
