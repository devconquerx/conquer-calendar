"""El código deja de usar Lead.neverbounce_result y la caché de verificaciones.

Solo cambia el estado de Django: la columna y la tabla siguen en la BD para que
el color viejo (que aún las lee y escribe) conviva con este durante el
despliegue azul/verde (expand → contract, docs/deploy-zero-downtime.md). Se
borran en la migración 0006, en un despliegue posterior y después de haber
ejecutado `exportar_verificaciones`.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0004_emailverificationcache'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='lead', name='neverbounce_result'),
                migrations.DeleteModel(name='EmailVerificationCache'),
            ],
            database_operations=[],
        ),
    ]
