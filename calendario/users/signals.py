from datetime import time

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


DISPONIBILIDAD_DEFAULT = [
    (0, time(0, 0), time(23, 59)),  # Lunes
    (1, time(0, 0), time(23, 59)),  # Martes
    (2, time(0, 0), time(23, 59)),  # Miércoles
    (3, time(0, 0), time(23, 59)),  # Jueves
    (4, time(0, 0), time(23, 59)),  # Viernes
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
