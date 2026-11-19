from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0044_recordatorios_sms'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='fechas_bloqueadas',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Fechas AAAA-MM-DD en las que este evento no ofrece horas, aunque los '
                          'organizadores estén disponibles. Cuentan en la zona del dueño del evento.',
                verbose_name='Días bloqueados',
            ),
        ),
    ]
