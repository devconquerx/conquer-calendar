# Solo cambia la etiqueta de sync_gcal: ahora ese origen cubre también el
# rechazo del invitado, no solo el del host. El valor guardado no cambia, así
# que no toca ninguna fila.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0029_cancelacionreserva'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cancelacionreserva',
            name='origen',
            field=models.CharField(
                choices=[
                    ('panel', 'Panel interno'),
                    ('publica', 'El invitado, desde su enlace'),
                    ('sync_gcal', 'Rechazo en Google Calendar'),
                    ('comando', 'Comando de mantenimiento'),
                    ('reagendada', 'Reagendada (se movió a otra hora)'),
                    ('desconocido', 'Sin identificar'),
                ],
                default='desconocido',
                max_length=20,
            ),
        ),
    ]
