# -*- coding: utf-8 -*-
"""Renombra el slug de Conquer AI: `blocks-ai-eu` → `ai-eu`.

0030 lo sembró como `blocks-ai-eu` para que la marca se detectara por el propio
slug (el tema sale de ahí). Pero el slug es también el nombre con el que el
funnel viaja fuera del calendario —es lo que se traduce al código de funnel del
CRM— y ahí el criterio es el del resto: `legal-eu` → `cg-eu`, `finance-eu` →
`fi-eu`. Conquer AI es su propio funnel, así que le toca `ai-eu`, que además va
tal cual al CRM sin traducción.

La detección de marca no se pierde: se resuelve por la ESCUELA (`conquer-ai`),
que es la primera pista que consulta `getTheme`, y `frontend/src/themes/index.js`
reconoce además el slug pelado.

Va en una migración aparte y no editando 0030 porque 0030 ya corrió en
producción (desplegada el 2026-09-10): la fila existe allí con el slug viejo y
hay que moverla, no re-sembrarla.

Idempotente y sin pérdida: solo toca la fila si sigue con el slug viejo. Nada
apunta al slug por valor —`Prellamada` enlaza el funnel por clave ajena y
`Lead.funnel` guarda el código del CRM, no el slug—, así que renombrarlo no
deja nada huérfano.
"""
from django.db import migrations

KEY = 'FullAiEu'
SLUG_VIEJO = 'blocks-ai-eu'
SLUG_NUEVO = 'ai-eu'


def _renombrar(apps, desde, hasta):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    FunnelForm.objects.filter(key=KEY, slug=desde).update(slug=hasta)


def forwards(apps, schema_editor):
    _renombrar(apps, SLUG_VIEJO, SLUG_NUEVO)


def backwards(apps, schema_editor):
    _renombrar(apps, SLUG_NUEVO, SLUG_VIEJO)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0030_seed_ai_eu'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
