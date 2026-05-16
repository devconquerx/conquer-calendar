import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0005_add_slug_equipo'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='aviso_maximo_dias',
            field=models.PositiveSmallIntegerField(
                default=60,
                help_text='Rango máximo (rolling) en días contados al minuto desde el momento actual.',
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(365),
                ],
            ),
        ),
    ]
