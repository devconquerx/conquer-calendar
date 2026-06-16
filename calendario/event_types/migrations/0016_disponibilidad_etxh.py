from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0015_add_formato_titulo_gcal'),
    ]

    operations = [
        migrations.CreateModel(
            name='DisponibilidadEtxh',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dia_semana', models.PositiveSmallIntegerField(choices=[
                    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
                    (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
                ])),
                ('hora_inicio', models.TimeField()),
                ('hora_fin', models.TimeField()),
                ('etxh', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='disponibilidad',
                    to='event_types.eventtypexhost',
                )),
            ],
            options={
                'db_table': 'disponibilidad_etxh',
                'ordering': ['dia_semana', 'hora_inicio'],
            },
        ),
    ]
