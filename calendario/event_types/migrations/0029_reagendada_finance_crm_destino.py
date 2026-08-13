from django.db import migrations


# EventTypes "Reagendada - Conquer Finance <región>" — ya existían (slug
# idéntico a los viejos links de reagendada de Calendly), solo sin conectar
# al CRM. No pasan por score_ranges (el reagendamiento no es parte del
# scoring del funnel, lo genera el CRM directo desde un Schedule existente).
REAGENDADA_FINANCE_IDS = (132, 96, 98)  # EU, LATAM, USA


def conectar(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(pk__in=REAGENDADA_FINANCE_IDS).update(crm_destino='schedule')


def revertir(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(pk__in=REAGENDADA_FINANCE_IDS).update(crm_destino='none')


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0028_eventtype_mostrar_caja_comentarios_and_more'),
    ]

    operations = [
        migrations.RunPython(conectar, revertir),
    ]
