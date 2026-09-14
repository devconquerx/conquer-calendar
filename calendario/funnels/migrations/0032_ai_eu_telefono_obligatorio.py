# -*- coding: utf-8 -*-
"""Conquer AI pide el teléfono siempre y obligatorio, sin checkbox.

La landing nació clonando la de Blocks EU y con ella se trajo
`landing.whatsappOptin: true`: el número solo se pedía si el visitante marcaba
el check de WhatsApp. Aquí se quiere el campo visible y obligatorio de entrada,
y sin nada que marcar.

Va por config y no por el catálogo de experimentos (`lib/formVariant.js`)
porque NO es un A/B: es el comportamiento fijo de este funnel. Llegó a tener uno
el 14/09/2026 con los códigos 77/78; se retiró el mismo día y esos códigos no se
reciclan.

`consentText` se fija a la redacción que menciona WhatsApp —la misma que usa
Finance EU al pedir el número— porque el texto por defecto solo habla del correo
y aquí se pide el móvil de entrada.

Se parchea la fila en BD porque el `landing` de estos funnels sólo vive ahí: los
JSON de seed no lo traen y corregirlos no llegaría a las filas desplegadas
(mismo motivo que 0003/0012/0019/0020/0024/0025/0027).
"""
from django.db import migrations

FORM_KEY = 'FullAiEu'

CONSENT_WHATSAPP = (
    'Al continuar aceptas que te enviemos tips, la repetición de la clase y '
    'recursos exclusivos por email/whatsapp. (Tranqui, solo contenido útil, '
    'nada de spam).'
)


def _patch(apps, landing_nuevo):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    form = FunnelForm.objects.filter(key=FORM_KEY).first()
    if not form:
        return
    config = form.config or {}
    landing = dict(config.get('landing') or {})
    landing_nuevo(landing)
    config['landing'] = landing
    form.config = config
    form.save(update_fields=['config'])


def forwards(apps, schema_editor):
    def aplicar(landing):
        landing.pop('whatsappOptin', None)
        landing['phoneRequired'] = True
        landing['consentText'] = CONSENT_WHATSAPP
    _patch(apps, aplicar)


def backwards(apps, schema_editor):
    def revertir(landing):
        landing.pop('phoneRequired', None)
        landing.pop('consentText', None)
        landing['whatsappOptin'] = True
    _patch(apps, revertir)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0031_ai_eu_slug'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
