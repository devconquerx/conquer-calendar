from django.db import migrations


# 89 y 90 son los EventTypes reales de PropTradingLatam (conectados en
# score_ranges), pero ninguno tenía slug_equipo — no existía página pública
# de reserva directa para ninguno de los dos. slug_equipo es único en la
# base, así que no se puede reusar el slug "limpio" que ya tiene el 99
# (duplicado suelto, sin tocar). Se les da uno propio, sufijado con su id
# para que no choque con nada.
SLUG_EQUIPO_POR_ID = {
    89: 'sesion-de-consultoria-conquer-finance-latam-89',
    90: 'sesion-de-consultoria-conquer-finance-latam-90',
}


def poner_slugs(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    for pk, slug_equipo in SLUG_EQUIPO_POR_ID.items():
        EventType.objects.filter(pk=pk).update(slug_equipo=slug_equipo)


def revertir(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(pk__in=SLUG_EQUIPO_POR_ID.keys()).update(slug_equipo=None)


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0029_reagendada_finance_crm_destino'),
    ]

    operations = [
        migrations.RunPython(poner_slugs, revertir),
    ]
