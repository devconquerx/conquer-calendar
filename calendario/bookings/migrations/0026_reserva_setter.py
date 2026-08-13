from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0025_reserva_asistencia_confirmada'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='setter',
            field=models.CharField(blank=True, default='', max_length=140),
        ),
    ]
