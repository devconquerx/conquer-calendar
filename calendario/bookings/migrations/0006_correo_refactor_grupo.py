from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0005_correo_plantilla_config_log'),
        ('grupos', '0003_grupo_bloqueos_v2'),
    ]

    operations = [
        # PlantillaCorreo: quitar logo_url y color_primario, añadir logo + recordatorios
        migrations.RemoveField(model_name='plantillacorreo', name='logo_url'),
        migrations.RemoveField(model_name='plantillacorreo', name='color_primario'),
        migrations.AddField(
            model_name='plantillacorreo',
            name='logo',
            field=models.FileField(blank=True, null=True, upload_to='plantillas_correo/'),
        ),
        migrations.AddField(
            model_name='plantillacorreo',
            name='recordatorio_1_activo',
            field=models.BooleanField(default=True, verbose_name='Recordatorio 1 activo'),
        ),
        migrations.AddField(
            model_name='plantillacorreo',
            name='recordatorio_1_horas',
            field=models.PositiveSmallIntegerField(default=24, verbose_name='Recordatorio 1 — horas antes'),
        ),
        migrations.AddField(
            model_name='plantillacorreo',
            name='recordatorio_2_activo',
            field=models.BooleanField(default=False, verbose_name='Recordatorio 2 activo'),
        ),
        migrations.AddField(
            model_name='plantillacorreo',
            name='recordatorio_2_horas',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='Recordatorio 2 — horas antes'),
        ),
        # PlantillaCorreo: añadir help_text al cuerpo
        migrations.AlterField(
            model_name='plantillacorreo',
            name='cuerpo',
            field=models.TextField(
                help_text=(
                    'Variables: {{nombre_invitado}}, {{email_invitado}}, {{nombre_host}}, '
                    '{{nombre_evento}}, {{fecha_hora}}, {{duracion}}, {{google_meet_url}}, {{link_cancelar}}'
                )
            ),
        ),
        # ConfigCorreoEvento: quitar campos de recordatorio
        migrations.RemoveField(model_name='configcorreoevento', name='recordatorio_1_activo'),
        migrations.RemoveField(model_name='configcorreoevento', name='recordatorio_1_horas'),
        migrations.RemoveField(model_name='configcorreoevento', name='recordatorio_2_activo'),
        migrations.RemoveField(model_name='configcorreoevento', name='recordatorio_2_horas'),
        # Actualizar verbose_name y help_text de las FK en ConfigCorreoEvento
        migrations.AlterField(
            model_name='configcorreoevento',
            name='plantilla_confirmacion_host',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='configs_confirmacion_host',
                to='bookings.plantillacorreo',
                verbose_name='Correo al host',
                help_text='Si no se selecciona, Google Calendar sigue enviando su correo por defecto.',
            ),
        ),
        migrations.AlterField(
            model_name='configcorreoevento',
            name='plantilla_confirmacion_inv',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='configs_confirmacion_inv',
                to='bookings.plantillacorreo',
                verbose_name='Correo al invitado',
                help_text='Si no se selecciona, Google Calendar sigue enviando su correo por defecto.',
            ),
        ),
        migrations.AlterField(
            model_name='configcorreoevento',
            name='plantilla_recordatorio',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='configs_recordatorio_evento',
                to='bookings.plantillacorreo',
                verbose_name='Plantilla de recordatorio',
                help_text='Los tiempos de envío se leen de la plantilla seleccionada.',
            ),
        ),
        # ConfigCorreoGrupo: nuevo modelo
        migrations.CreateModel(
            name='ConfigCorreoGrupo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grupo', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='config_correo',
                    to='grupos.grupo',
                )),
                ('plantilla_confirmacion_host', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='configs_grupo_confirmacion_host',
                    to='bookings.plantillacorreo',
                    verbose_name='Correo al host',
                    help_text='Se aplica a todos los miembros del grupo salvo que el evento tenga su propia config.',
                )),
                ('plantilla_confirmacion_inv', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='configs_grupo_confirmacion_inv',
                    to='bookings.plantillacorreo',
                    verbose_name='Correo al invitado',
                )),
                ('plantilla_recordatorio', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='configs_grupo_recordatorio',
                    to='bookings.plantillacorreo',
                    verbose_name='Plantilla de recordatorio',
                )),
            ],
            options={
                'verbose_name': 'Configuración de correo por grupo',
                'verbose_name_plural': 'Configuraciones de correo por grupo',
                'db_table': 'config_correo_grupo',
            },
        ),
    ]
