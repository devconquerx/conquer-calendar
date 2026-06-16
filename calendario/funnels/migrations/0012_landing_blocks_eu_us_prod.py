# -*- coding: utf-8 -*-
# Alinea la landing de conquer-blocks en las regiones EU y US con producción
# (www.conquerblocks.com). LATAM ya quedó alineada en 0003; EU/US se habían
# quedado con dos textos distintos a los de prod:
#   - bullet 3: terminaba en "...familia gracias al trabajo remoto." cuando en
#     prod (las 3 regiones) es "...tiempo para ti y tu familia."
#   - rol del instructor: faltaba el prefijo "Bienvenido es ".
# Se parchean SOLO esos dos campos para no tocar el titular, que es propio de
# cada región (salario 71%/98,7% en EU, $10,000/100% en US).
from django.db import migrations

NEW_BULLET_3 = "Descubre una nueva vía para tener más libertad, <strong>tiempo para ti y tu familia.</strong>"
NEW_ROLE = "Bienvenido es Director de Educación Tecnológica en Conquer Blocks."

OLD_BULLET_3 = "Descubre una nueva vía para tener más libertad, tiempo para ti y tu familia gracias al trabajo remoto."
OLD_ROLE = "Director de Educación Tecnológica en Conquer Blocks."


def _patch(apps, bullet_3, role):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for ff in FunnelForm.objects.filter(escuela='conquer-blocks', region__in=['eu', 'us']):
        cfg = ff.config or {}
        landing = cfg.get('landing')
        if not isinstance(landing, dict):
            continue
        bullets = landing.get('bullets')
        if isinstance(bullets, list) and len(bullets) >= 3:
            bullets[2] = bullet_3
            landing['bullets'] = bullets
        instructor = landing.get('instructor')
        if isinstance(instructor, dict):
            instructor['role'] = role
            landing['instructor'] = instructor
        cfg['landing'] = landing
        ff.config = cfg
        ff.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _patch(apps, NEW_BULLET_3, NEW_ROLE)


def backwards(apps, schema_editor):
    _patch(apps, OLD_BULLET_3, OLD_ROLE)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0011_prellamada_event_id_prellamada_utm_adid_and_more'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
