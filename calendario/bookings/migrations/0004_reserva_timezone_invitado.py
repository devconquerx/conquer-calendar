from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0003_reserva_telefono_invitado'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='timezone_invitado',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
