from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_reserva_google_event_id_reserva_google_meet_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='telefono_invitado',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
