"""
Fuera las dos tablas de disponibilidad por evento×host.

Su contenido ya vive en horarios con nombre (migración 0035), que además son
reutilizables entre tipos de evento. Mantener las dos vías dejaba tres niveles
de precedencia imposibles de depurar.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0035_migrar_a_horarios_nombrados'),
        ('availability', '0007_bloques_solo_por_horario'),
    ]

    operations = [
        migrations.DeleteModel(name='DisponibilidadEtxh'),
        migrations.DeleteModel(name='DisponibilidadFechaEtxh'),
    ]
