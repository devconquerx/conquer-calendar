from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0004_reserva_timezone_invitado'),
        ('event_types', '0009_aviso_minimo_minutos'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlantillaCorreo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('logo_url', models.URLField(blank=True, default='')),
                ('color_primario', models.CharField(default='#000000', max_length=7)),
                ('texto_encabezado', models.CharField(max_length=200)),
                ('cuerpo', models.TextField()),
                ('pie_pagina', models.CharField(blank=True, default='', max_length=300)),
                ('activa', models.BooleanField(default=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Plantilla de correo',
                'verbose_name_plural': 'Plantillas de correo',
                'db_table': 'plantillas_correo',
            },
        ),
        migrations.CreateModel(
            name='ConfigCorreoEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recordatorio_1_activo', models.BooleanField(default=True)),
                ('recordatorio_1_horas', models.PositiveSmallIntegerField(default=24)),
                ('recordatorio_2_activo', models.BooleanField(default=False)),
                ('recordatorio_2_horas', models.PositiveSmallIntegerField(default=1)),
                ('event_type', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='config_correo',
                    to='event_types.eventtype',
                )),
                ('plantilla_confirmacion_host', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='configs_confirmacion_host',
                    to='bookings.plantillacorreo',
                )),
                ('plantilla_confirmacion_inv', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='configs_confirmacion_inv',
                    to='bookings.plantillacorreo',
                )),
                ('plantilla_recordatorio', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='configs_recordatorio_evento',
                    to='bookings.plantillacorreo',
                )),
            ],
            options={
                'verbose_name': 'Configuración de correo por evento',
                'verbose_name_plural': 'Configuraciones de correo por evento',
                'db_table': 'config_correo_evento',
            },
        ),
        migrations.CreateModel(
            name='LogCorreo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(
                    choices=[
                        ('confirmacion_host', 'Confirmación host'),
                        ('confirmacion_invitado', 'Confirmación invitado'),
                        ('recordatorio_1', 'Recordatorio 1'),
                        ('recordatorio_2', 'Recordatorio 2'),
                        ('cancelacion', 'Cancelación'),
                    ],
                    max_length=30,
                )),
                ('destinatario', models.EmailField()),
                ('enviado_en', models.DateTimeField(auto_now_add=True)),
                ('exitoso', models.BooleanField()),
                ('error_detalle', models.TextField(blank=True, default='')),
                ('plantilla', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='logs',
                    to='bookings.plantillacorreo',
                )),
                ('reserva', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='logs_correo',
                    to='bookings.reserva',
                )),
            ],
            options={
                'verbose_name': 'Log de correo',
                'verbose_name_plural': 'Logs de correo',
                'db_table': 'logs_correo',
                'ordering': ['-enviado_en'],
            },
        ),
    ]
