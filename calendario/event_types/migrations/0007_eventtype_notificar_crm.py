from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0006_aviso_maximo_dias'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='notificar_crm',
            field=models.BooleanField(default=False),
        ),
    ]
