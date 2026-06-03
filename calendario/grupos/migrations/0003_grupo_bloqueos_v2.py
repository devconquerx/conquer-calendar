from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grupos', '0002_grupo_bloqueos'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupo',
            name='bloquear_editar_disponibilidad',
            field=models.BooleanField(default=False, verbose_name='Bloquear edición de disponibilidad'),
        ),
        migrations.AddField(
            model_name='grupo',
            name='bloquear_crear_event_types',
            field=models.BooleanField(default=False, verbose_name='Bloquear creación de tipos de evento'),
        ),
        migrations.AddField(
            model_name='grupo',
            name='bloquear_activar_event_types',
            field=models.BooleanField(default=False, verbose_name='Bloquear activar/desactivar tipos de evento'),
        ),
    ]
