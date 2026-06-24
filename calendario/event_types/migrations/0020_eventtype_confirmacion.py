from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0019_eventtype_crm_destino_consolidate'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='confirmacion_tipo',
            field=models.CharField(
                choices=[('default', 'Página de confirmación'), ('url', 'URL personalizada')],
                default='default',
                help_text='A dónde se lleva al invitado después de reservar.',
                max_length=10,
                verbose_name='Redirección post-reserva',
            ),
        ),
        migrations.AddField(
            model_name='eventtype',
            name='confirmacion_url',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Path interno (ej: /conquer-blocks/confirmacion-llamada-latam/). Solo aplica si el tipo es "URL personalizada".',
                max_length=500,
                verbose_name='Path de confirmación',
            ),
        ),
    ]
