from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0014_enlace_unico'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='formato_titulo_gcal',
            field=models.CharField(
                choices=[
                    ('evento_invitado', 'Evento · Invitado  (ej: "Consultoría con Juan")'),
                    ('invitado_evento', 'Invitado · Evento  (ej: "Juan - Consultoría")'),
                ],
                default='evento_invitado',
                help_text='Orden del título que aparece en Google Calendar / Google Meet.',
                max_length=20,
            ),
        ),
    ]
