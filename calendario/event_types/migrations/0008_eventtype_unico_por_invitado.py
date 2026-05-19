from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0007_eventtype_notificar_crm'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='unico_por_invitado',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si está activo, un mismo email no puede reservar este "
                    "evento dos veces mientras tenga una reserva futura confirmada."
                ),
            ),
        ),
    ]
