from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0017_disponibilidad_fecha_etxh'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='crm_destino',
            field=models.CharField(
                choices=[('onboarding', 'Onboarding'), ('schedule', 'Schedule (llamada)')],
                default='onboarding',
                help_text=(
                    "A qué tabla del CRM se envía la reserva (solo aplica si 'Notificar al CRM' "
                    "está activo): Onboarding (default) o Schedule (la llamada de venta)."
                ),
                max_length=20,
            ),
        ),
    ]
