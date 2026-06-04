from django.db import migrations, models
import django.db.models.deletion


def crear_config_default(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    ConfigCorreoDefault = apps.get_model('bookings', 'ConfigCorreoDefault')

    host = PlantillaCorreo.objects.filter(nombre='Confirmación — Host').first()
    inv  = PlantillaCorreo.objects.filter(nombre='Confirmación — Invitado').first()
    rec  = PlantillaCorreo.objects.filter(nombre='Recordatorio de reserva').first()

    ConfigCorreoDefault.objects.update_or_create(
        pk=1,
        defaults={
            'plantilla_confirmacion_host': host,
            'plantilla_confirmacion_inv':  None,  # GCal maneja invitados por defecto
            'plantilla_recordatorio':      rec,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0015_actualizar_campos_visibles_plantillas'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigCorreoDefault',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('plantilla_confirmacion_host', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='default_confirmacion_host',
                    to='bookings.plantillacorreo',
                    verbose_name='Correo al host (por defecto)',
                )),
                ('plantilla_confirmacion_inv', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='default_confirmacion_inv',
                    to='bookings.plantillacorreo',
                    verbose_name='Correo al invitado (por defecto)',
                )),
                ('plantilla_recordatorio', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='default_recordatorio',
                    to='bookings.plantillacorreo',
                    verbose_name='Recordatorio (por defecto)',
                )),
            ],
            options={
                'verbose_name': 'Configuración global de correos',
                'verbose_name_plural': 'Configuración global de correos',
                'db_table': 'config_correo_default',
            },
        ),
        migrations.RunPython(crear_config_default, migrations.RunPython.noop),
    ]
