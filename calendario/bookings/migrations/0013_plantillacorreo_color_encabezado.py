from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0012_limpiar_cuerpos_info_card'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacorreo',
            name='color_encabezado',
            field=models.CharField(default='#111827', max_length=7, verbose_name='Color del encabezado'),
        ),
    ]
