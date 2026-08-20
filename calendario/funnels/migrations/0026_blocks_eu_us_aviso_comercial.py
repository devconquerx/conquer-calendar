# -*- coding: utf-8 -*-
"""Devuelve el aviso de comunicaciones comerciales a las landings EU y US de Blocks.

El párrafo "Al proporcionarnos tu correo electrónico, aceptas recibir
comunicaciones comerciales por parte de nuestra empresa" se había ocultado en
estas tres landings poniendo `landing.commercialConsent = False` (ver 5574e6f,
que sacó el texto del componente y lo hizo configurable por funnel). Negocio lo
quiere de vuelta en EU y US, como ya lo tiene LATAM.

Se quita la bandera en vez de ponerla a `True` porque el componente muestra el
aviso por defecto (`landing.commercialConsent !== false`): sin clave, la landing
queda como el resto y no arrastra una excepción que haya que recordar.

`blocks-eu-2` entra con `blocks-eu`: es la segunda landing EU y su `landing`
debe ser idéntico al de la principal (0024). La línea de la política de
privacidad no se toca: esa se muestra siempre, en todas.

Se parchea la fila porque `landing` sólo vive en la BD, igual que 0024/0025.
"""
from django.db import migrations

FORM_KEYS = ['FullEu', 'FullEu2', 'FullUs']


def _set(apps, ocultar):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for key in FORM_KEYS:
        form = FunnelForm.objects.filter(key=key).first()
        if not form:
            continue
        config = form.config or {}
        landing = dict(config.get('landing') or {})

        if ocultar:
            landing['commercialConsent'] = False
        else:
            landing.pop('commercialConsent', None)

        config['landing'] = landing
        form.config = config
        form.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _set(apps, ocultar=False)


def backwards(apps, schema_editor):
    _set(apps, ocultar=True)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0025_languages_eu_whatsapp_optin'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
