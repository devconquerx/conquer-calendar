from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0016_disponibilidad_etxh'),
    ]

    operations = [
        migrations.CreateModel(
            name='DisponibilidadFechaEtxh',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('hora_inicio', models.TimeField(blank=True, null=True)),
                ('hora_fin', models.TimeField(blank=True, null=True)),
                ('etxh', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='disponibilidad_fechas',
                    to='event_types.eventtypexhost',
                )),
            ],
            options={
                'db_table': 'disponibilidad_fecha_etxh',
                'ordering': ['fecha', 'hora_inicio'],
            },
        ),
    ]
