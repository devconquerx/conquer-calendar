from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0023_remove_reserva_uq_reserva_host_inicio_confirmada_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='asistencia_confirmada',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reserva',
            name='asistencia_confirmada_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
