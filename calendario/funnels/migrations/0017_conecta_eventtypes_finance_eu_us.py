from django.db import migrations


# EventTypes elegidos siguiendo la misma lógica que conquerx-funnels-new (un
# único evento cubre los dos tramos de score en EU, igual que allá los dos
# tramos apuntaban al mismo slug de Calendly; US solo tenía un tramo).
EVENT_TYPE_BY_FUNNEL_KEY = {
    'PropTradingEu': 92,
    'PropTradingUs': 103,
}


def conectar_event_types(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    EventType = apps.get_model('event_types', 'EventType')

    for key, event_type_id in EVENT_TYPE_BY_FUNNEL_KEY.items():
        funnel = FunnelForm.objects.filter(key=key).first()
        if not funnel:
            continue
        config = funnel.config or {}
        ranges = config.get('score_ranges') or []
        for rango in ranges:
            rango['event_type_id'] = event_type_id
            rango['calendly_url'] = None
        config['score_ranges'] = ranges
        funnel.config = config
        funnel.save(update_fields=['config'])

        EventType.objects.filter(pk=event_type_id).update(crm_destino='schedule')


def revertir(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')

    # Restaura los calendly_url originales (los event_type_id se dejan puestos
    # a propósito: no hacen daño con calendly_url ya presente, y así no se
    # pierde el dato de qué EventType se había elegido si se vuelve a migrar).
    ORIGINAL_CALENDLY_URLS = {
        'PropTradingEu': [
            'https://calendly.com/d/cnt6-mc9-ffy/sesion-de-consultoria-conquer-finance-eu',
            'https://calendly.com/d/ck24-gd9-f2z/sesion-de-consultoria-conquer-finance-eu',
        ],
        'PropTradingUs': [
            'https://calendly.com/d/3q2-8bx-c98/sesion-de-consultoria-conquer-finance-us',
        ],
    }
    for key, urls in ORIGINAL_CALENDLY_URLS.items():
        funnel = FunnelForm.objects.filter(key=key).first()
        if not funnel:
            continue
        config = funnel.config or {}
        ranges = config.get('score_ranges') or []
        for rango, url in zip(ranges, urls):
            rango['calendly_url'] = url
        config['score_ranges'] = ranges
        funnel.config = config
        funnel.save(update_fields=['config'])


class Migration(migrations.Migration):

    dependencies = [
        ('funnels', '0016_finance_eu_landing_video'),
        ('event_types', '0028_eventtype_mostrar_caja_comentarios_and_more'),
    ]

    operations = [
        migrations.RunPython(conectar_event_types, revertir),
    ]
