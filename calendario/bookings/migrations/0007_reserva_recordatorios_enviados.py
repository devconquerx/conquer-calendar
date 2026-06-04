from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0006_correo_refactor_grupo'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='recordatorio_1_enviado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reserva',
            name='recordatorio_2_enviado',
            field=models.BooleanField(default=False),
        ),
    ]
