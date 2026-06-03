from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grupos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='grupo',
            name='bloquear_editar_event_types',
            field=models.BooleanField(default=False, verbose_name='Bloquear edición de tipos de evento'),
        ),
        migrations.AddField(
            model_name='grupo',
            name='bloquear_eliminar_event_types',
            field=models.BooleanField(default=False, verbose_name='Bloquear eliminación de tipos de evento'),
        ),
        migrations.AddField(
            model_name='grupo',
            name='bloquear_cancelar_reservas',
            field=models.BooleanField(default=False, verbose_name='Bloquear cancelación de reservas propias'),
        ),
    ]
