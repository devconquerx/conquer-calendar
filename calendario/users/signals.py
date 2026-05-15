from datetime import time

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


DISPONIBILIDAD_DEFAULT = [
    (0, time(8, 0), time(16, 0)),  # Lunes
    (1, time(8, 0), time(16, 0)),  # Martes
    (2, time(8, 0), time(16, 0)),  # Miércoles
    (3, time(8, 0), time(16, 0)),  # Jueves
    (4, time(8, 0), time(16, 0)),  # Viernes
]


@receiver(post_save, sender=User)
def crear_disponibilidad_default(sender, instance, created, **kwargs):
    if not created:
        return
    from calendario.availability.models import BloqueHorarioSemanal
    BloqueHorarioSemanal.objects.bulk_create([
        BloqueHorarioSemanal(
            host=instance,
            dia_semana=dia,
            hora_inicio=inicio,
            hora_fin=fin,
        )
        for dia, inicio, fin in DISPONIBILIDAD_DEFAULT
    ], ignore_conflicts=True)
