import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """Abre el rango de `prioridad` a 0 = organizador excluido del reparto.

    Solo cambia validadores y help_text: los datos existentes (1..3) siguen
    siendo válidos y nadie pasa a 0 por esta migración.
    """

    dependencies = [
        ('event_types', '0025_incremento_choices_40_45'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventtypexhost',
            name='prioridad',
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(3),
                ],
                verbose_name='Prioridad en el round-robin',
                help_text=(
                    'De 1 a 3, donde 3 es la más alta. Cuando varios organizadores '
                    'están libres a la misma hora, la reserva se asigna al de mayor '
                    'prioridad; a igualdad de prioridad decide el reparto de carga de '
                    'siempre. 0 lo deja fuera de este evento: no recibe reservas ni '
                    'ofrece sus horas hasta que se le ponga un número mayor que 0.'
                ),
            ),
        ),
    ]
