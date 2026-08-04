from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0024_remove_eventtype_max_reservas_por_slot_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventtype',
            name='incremento_inicio_minutos',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (15, '15 minutos'),
                    (20, '20 minutos'),
                    (30, '30 minutos'),
                    (40, '40 minutos'),
                    (45, '45 minutos'),
                    (60, '60 minutos'),
                ],
                default=30,
                help_text='Cada cuántos minutos aparece un slot disponible.',
            ),
        ),
    ]
