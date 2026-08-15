# -*- coding: utf-8 -*-
"""Conecta las 4 regiones de Blocks a UN EventType de prueba (placeholder).

Objetivo: validar el pipeline reserva→AC/Respond.io/ads (que hoy nunca se
dispara para Blocks porque no existe ninguna `Reserva` interna, ver
[[funnel-blocks-eu-eu2-alignment]]/conversación). El host real y el/los
EventType(s) definitivos por región quedan pendientes de decisión — esto
es un placeholder explícito ("(TEST)" en el nombre) para probar el flujo,
NO el evento final. Antes de dar por cerrado esto: reemplazar
`EVENTO_PRUEBA_SLUG` por los EventTypes reales por región (posiblemente 2
para LATAM, como el viejo) y borrar este placeholder.

Mismo patrón que `0017_conecta_eventtypes_finance_eu_us.py`: setea
`event_type_id` y limpia `calendly_url` en cada rango.
"""
from django.db import migrations

EVENTO_PRUEBA_SLUG = 'sesion-de-consultoria-conquer-blocks-test'
HOST_USERNAME = 'jose.andres'

FUNNEL_KEYS = ['FullLatam', 'FullEu', 'FullEu2', 'FullUs']


def crear_y_conectar(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    User = apps.get_model('users', 'User')
    FunnelForm = apps.get_model('funnels', 'FunnelForm')

    host = User.objects.filter(username=HOST_USERNAME).first()
    if not host:
        return

    evento, _ = EventType.objects.get_or_create(
        slug=EVENTO_PRUEBA_SLUG,
        defaults=dict(
            host=host,
            nombre='Sesión de Consultoría | Conquer Blocks (TEST)',
            duracion_minutos=45,
            incremento_inicio_minutos=45,
            buffer_antes_minutos=0,
            buffer_despues_minutos=0,
            aviso_minimo_minutos=0,
            aviso_maximo_dias=60,
            rango_tipo='rolling',
            formato_titulo_gcal='evento_invitado',
            activo=True,
            crm_destino='schedule',
            confirmacion_tipo='default',
            unico_por_invitado=True,
        ),
    )

    for key in FUNNEL_KEYS:
        f = FunnelForm.objects.filter(key=key).first()
        if not f:
            continue
        config = f.config or {}
        ranges = config.get('score_ranges') or []
        for rango in ranges:
            rango['event_type_id'] = evento.id
            rango['calendly_url'] = None
        config['score_ranges'] = ranges
        f.config = config
        f.save(update_fields=['config'])


def desconectar(apps, schema_editor):
    # No-op: no restauramos calendly_url aquí (a diferencia de 0017, este es
    # un placeholder explícito sin URLs "originales" que restaurar de forma
    # significativa — los calendly_url siguen disponibles en blocks_*.json).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0022_blocks_video_por_region'),
    ]
    operations = [
        migrations.RunPython(crear_y_conectar, desconectar),
    ]
