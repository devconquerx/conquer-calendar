# -*- coding: utf-8 -*-
"""Activa el check opcional de WhatsApp en la landing de Conquer Languages EU.

Es el mismo check que Conquer Blocks EU ("OPCIONAL: Envíame un acceso directo
a la repetición por WhatsApp"), que al marcarse revela el campo de teléfono y
lo hace obligatorio, manda `wants_whatsapp` al backend y desactiva el honeypot
mientras el campo está visible. En Blocks es la rama de test de un A/B
(`form_variant_cb_eu`, variante 52); aquí NO hay experimento: va fijo para
todos los visitantes de `languages-eu`.

`LandingForm.jsx` ya contempla las dos formas de encenderlo — `landing.whatsappOptin`
manda sobre la lógica de A/B/marca — así que basta con poner la bandera en la
config del funnel; no hace falta tocar el catálogo de experimentos.

Se parchea la fila existente en vez de tocar `seed_data/languages_eu.json`
porque el `landing` de Languages (título, bullets, instructor…) sólo vive en
la BD: el JSON de seed nunca lo trajo, así que corregirlo no llegaría a las
filas ya desplegadas (mismo motivo que 0003/0012/0019/0020/0024).
"""
from django.db import migrations

FORM_KEY = 'EnglishEu'


def _set_optin(apps, valor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    form = FunnelForm.objects.filter(key=FORM_KEY).first()
    if not form:
        return

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
    # Quita la bandera del todo: sin ella la landing vuelve al comportamiento
    # por defecto (sin check, teléfono sólo por honeypot).
    _set_optin(apps, None)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0024_blocks_eu_2_landing_igual_a_eu'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
