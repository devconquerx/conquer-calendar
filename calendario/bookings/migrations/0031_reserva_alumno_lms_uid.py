from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0030_cancelacion_origen_rechazo_gcal'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='alumno_lms_uid',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='ID del alumno en la academia'),
        ),
    ]
