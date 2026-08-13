from django.db import migrations


# 89 es el EventType real de PropTradingLatam (conectado en score_ranges),
# pero no tenía slug_equipo — no existía página pública de reserva directa.
# slug_equipo es único en la base, así que no se puede reusar el slug
# "limpio" que ya tiene el 99 (duplicado suelto, sin tocar). Se le da uno
# propio, sufijado con su id para que no choque con nada.
#
# (90 — el otro EventType que originalmente iba acá — se borró: era
# "⭐ Sesión de Consultoría LATAM" de jose.andres, con solo reservas de
# prueba. Su tramo de score se fusionó con el 89 en la migración 0031.)
SLUG_EQUIPO_POR_ID = {
    89: 'sesion-de-consultoria-conquer-finance-latam-89',
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
