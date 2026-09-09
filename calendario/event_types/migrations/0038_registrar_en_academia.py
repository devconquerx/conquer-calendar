from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0037_acceso_transicion'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='registrar_en_academia',
            field=models.BooleanField(default=False, help_text='Cada reserva de este tipo de evento se envía a la academia al agendarse, y también al cancelarse o reagendarse. Es de donde salen las métricas de los profesores.', verbose_name='Registrar las sesiones en la academia'),
        ),
    ]
