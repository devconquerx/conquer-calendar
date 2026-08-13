from django.db import migrations


# El EventType 90 ("⭐ Sesión de Consultoría | Conquer Finance LATAM", el
# tramo de score 2-2.9) se borró en prod — solo tenía reservas de prueba.
# Este tramo se fusiona con el 89 (score 3-100): las dos regiones restantes
# de Finance (EU, US) ya usaban un único EventType para todos los tramos de
# score, esto solo iguala a LATAM con ese mismo patrón.
def fusionar(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    f = FunnelForm.objects.filter(key='PropTradingLatam').first()
    if not f:
        return
    config = f.config or {}
    ranges = config.get('score_ranges') or []
    for rango in ranges:
        if rango.get('event_type_id') == 90:
            rango['event_type_id'] = 89
    config['score_ranges'] = ranges
    f.config = config
    f.save(update_fields=['config'])


def revertir(apps, schema_editor):
    # No hay vuelta atrás real: el EventType 90 ya no existe. Deja el estado
    # fusionado (revertir a un event_type_id inexistente sería peor).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0017_conecta_eventtypes_finance_eu_us'),
    ]

    operations = [
        migrations.RunPython(fusionar, revertir),
    ]
