from django.db import migrations, models


def set_destino(apps, schema_editor):
    """Mapea el viejo notificar_crm al nuevo crm_destino, preservando la config:
    - notificar_crm=False → 'none' (no enviar)
    - notificar_crm=True  → mantiene su crm_destino actual ('onboarding'/'schedule');
      si por algún motivo quedó en 'none', cae a 'onboarding' (comportamiento previo)."""
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(notificar_crm=False).update(crm_destino='none')
    EventType.objects.filter(notificar_crm=True, crm_destino='none').update(crm_destino='onboarding')


def reverse_destino(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    EventType.objects.filter(crm_destino='none').update(notificar_crm=False)
    EventType.objects.exclude(crm_destino='none').update(notificar_crm=True)


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0018_eventtype_crm_destino'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventtype',
            name='crm_destino',
            field=models.CharField(
                choices=[
                    ('none', 'No enviar al CRM'),
                    ('onboarding', 'Onboarding'),
                    ('schedule', 'Schedule (llamada)'),
                ],
                default='none',
                max_length=20,
                verbose_name='Destino en el CRM',
                help_text=(
                    "A qué tabla del CRM se envía la reserva al agendarse: 'No enviar' "
                    "(default, no va al CRM), 'Onboarding', o 'Schedule' (la llamada de venta; "
                    "además dispara las conversiones a redes/ActiveCampaign/Respond.io)."
                ),
            ),
        ),
        migrations.RunPython(set_destino, reverse_destino),
        migrations.RemoveField(
            model_name='eventtype',
            name='notificar_crm',
        ),
    ]
