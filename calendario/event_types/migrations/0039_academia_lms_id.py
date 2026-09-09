from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0038_registrar_en_academia'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='academia_lms_id',
            field=models.PositiveIntegerField(blank=True, help_text='Id numérico de la academia (Academy) a la que pertenecen estas sesiones. Lo da el equipo de la academia. Vacío = que lo resuelvan ellos por el profesor.', null=True, verbose_name='ID de la academia en el LMS'),
        ),
    ]
