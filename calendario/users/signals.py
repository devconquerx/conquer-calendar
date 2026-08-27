import logging
from datetime import time

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User

logger = logging.getLogger(__name__)

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
    from calendario.availability.models import BloqueHorarioSemanal, Horario

    # Todo el mundo nace con un horario "Default": es al que caen los tipos de
    # evento que no tienen uno asignado, así que sin él no habría huecos.
    horario, _ = Horario.objects.get_or_create(
        host=instance,
        nombre=Horario.NOMBRE_DEFAULT,
        defaults={'es_default': True},
    )
    BloqueHorarioSemanal.objects.bulk_create([
        BloqueHorarioSemanal(
            horario=horario,
            dia_semana=dia,
            hora_inicio=inicio,
            hora_fin=fin,
        )
        for dia, inicio, fin in DISPONIBILIDAD_DEFAULT
    ], ignore_conflicts=True)


@receiver(post_save, sender=User)
def inicializar_gcal(sender, instance, created, **kwargs):
    from django.conf import settings

    # raw=True durante loaddata — saltamos para no interferir con la restauración
    if not created or kwargs.get('raw'):
        return
    # En los tests no se sale a Google: casi todos crean un host en su setUp y
    # cada uno se llevaba ~0,4 s esperando a que las credenciales de prueba
    # fallaran con invalid_grant. Eran más de 50 s de los 250 de la suite, sin
    # probar nada. Los tests que quieran esta ruta pueden forzarla con
    # override_settings(TESTING=False) o llamando al sync directamente.
    if getattr(settings, 'TESTING', False):
        return
    try:
        from calendario.google_calendar.sync import sincronizar_host_completo, registrar_canal_watch
        sincronizar_host_completo(instance)
        webhook_url = getattr(settings, 'GCAL_WEBHOOK_URL', '')
        if webhook_url:
            registrar_canal_watch(instance, webhook_url)
    except Exception:
        logger.exception('inicializar_gcal: error al sincronizar host=%s', instance.email)
