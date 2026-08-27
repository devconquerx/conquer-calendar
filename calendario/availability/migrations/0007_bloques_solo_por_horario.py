"""
Los bloques dejan de colgar del host y cuelgan solo del horario.

El `horario` pasa a obligatorio (la migración de datos anterior ya lo rellenó en
todas las filas) y el FK a `host` desaparece: la persona se alcanza por
`bloque.horario.host`, sin dos caminos que puedan contradecirse.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('availability', '0006_alter_bloquehorariofecha_options_and_more'),
        # El RunPython que puebla `horario` tiene que haber corrido antes de que
        # el campo se vuelva obligatorio.
        ('event_types', '0035_migrar_a_horarios_nombrados'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bloquehorariosemanal',
            name='horario',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bloques_semanales',
                to='availability.horario',
            ),
        ),
        migrations.AlterField(
            model_name='bloquehorariofecha',
            name='horario',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bloques_fecha',
                to='availability.horario',
            ),
        ),
        migrations.RemoveField(
            model_name='bloquehorariosemanal',
            name='host',
        ),
        migrations.RemoveField(
            model_name='bloquehorariofecha',
            name='host',
        ),
    ]
