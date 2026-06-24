"""Configura confirmacion_tipo='url' en los EventTypes que ya se usan
desde funnels, replicando la lógica hardcodeada de confirmacion_url()."""

from django.db import migrations

_ESCUELAS_RUTA_PATH = ('conquer-blocks', 'conquer-legal')


def _confirmacion_url(escuela, region):
    if escuela == 'conquer-legal':
        return '/hub/confirmacion'
    if escuela in _ESCUELAS_RUTA_PATH:
        return f'/{escuela}/confirmacion-llamada-{region}/'
    return f'/confirmacion-llamada-{region}/'


def forward(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    Prellamada = apps.get_model('funnels', 'Prellamada')

    et_ids = (
        Prellamada.objects
        .exclude(event_type=None)
        .exclude(funnel=None)
        .values_list('event_type_id', flat=True)
        .distinct()
    )

    for et_id in et_ids:
        pares = (
            Prellamada.objects
            .filter(event_type_id=et_id)
            .exclude(funnel=None)
            .values_list('funnel__escuela', 'funnel__region')
            .distinct()
        )
        pares = list(pares)
        if len(pares) != 1:
            continue
        escuela, region = pares[0]
        url = _confirmacion_url(escuela, region)
        EventType.objects.filter(pk=et_id).update(
            confirmacion_tipo='url',
            confirmacion_url=url,
        )


def backward(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(confirmacion_tipo='url').update(
        confirmacion_tipo='default',
        confirmacion_url='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0020_eventtype_confirmacion'),
        ('funnels', '0012_landing_blocks_eu_us_prod'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
