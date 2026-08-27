# -*- coding: utf-8 -*-
"""Apaga el A/B del checkbox de WhatsApp en Blocks EU dejando la rama ganadora.

Las dos landings de Europa (`blocks-eu` y `blocks-eu-2`) probaban si pedir el
teléfono con el check opcional de WhatsApp convertía mejor que no pedirlo
(variantes 51/52 y 53/54). El test se da por terminado con la rama CON checkbox
como ganadora, así que deja de ser una rama de experimento y pasa a ser fija
para todos los visitantes.

Va por `landing.whatsappOptin` —el override de config que ya manda sobre la
lógica de A/B y de marca en `LandingForm.jsx`, el mismo que usó 0025 para
Languages EU— en vez de por el catálogo de experimentos. Así el checkbox queda
desligado del A/B y `utm_form_variant` queda libre para el test de fondo blanco
que entra en su lugar (69/70 y 71/72, en `lib/formVariant.js`).

Se parchea la fila en BD porque el `landing` de estos funnels sólo vive ahí:
los JSON de seed no lo traen y corregirlos no llegaría a las filas desplegadas
(mismo motivo que 0003/0012/0019/0020/0024/0025).
"""
from django.db import migrations

FORM_KEYS = ('FullEu', 'FullEu2')


def _set_optin(apps, valor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for form in FunnelForm.objects.filter(key__in=FORM_KEYS):
        config = form.config or {}
        landing = dict(config.get('landing') or {})

        if valor is None:
            landing.pop('whatsappOptin', None)
        else:
            landing['whatsappOptin'] = valor

        config['landing'] = landing
        form.config = config
        form.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _set_optin(apps, True)


def backwards(apps, schema_editor):
    # Sin la bandera, el checkbox vuelve a depender del experimento; como el
    # nuevo ya no lo declara, la landing se quedaría sin él.
    _set_optin(apps, None)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0026_blocks_eu_us_aviso_comercial'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
