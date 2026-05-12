from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('availability', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='bloquehorariosemanal',
            index=models.Index(fields=['host', 'dia_semana'], name='ix_bloque_host_dia'),
        ),
    ]
