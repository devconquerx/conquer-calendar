"""
Helpers compartidos para crear objetos de prueba.
Emails reales: santiago.tovar@conquerx.com (host) / santiagocentenot@gmail.com (invitado).
"""
from datetime import date, time, datetime, timezone, timedelta

from calendario.users.models import User
from calendario.permisos.models import Rol, RolXUsuario
from calendario.event_types.models import EventType, EventTypeXHost
from calendario.availability.models import BloqueHorarioSemanal
from calendario.bookings.models import Reserva


EMAIL_HOST = 'santiago.tovar@conquerx.com'
EMAIL_INVITADO = 'santiagocentenot@gmail.com'
NOMBRE_INVITADO = 'Santiago Centeno'


def crear_rol_host():
    rol, _ = Rol.objects.get_or_create(nombre='host', defaults={'descripcion': 'Host de calendario'})
    return rol


def crear_host(email=EMAIL_HOST, first_name='Santiago', last_name='Tovar'):
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': email.split('@')[0],
            'first_name': first_name,
            'last_name': last_name,
            'is_active': True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    rol = crear_rol_host()
    RolXUsuario.objects.get_or_create(usuario=user, rol=rol)
    return user


def crear_event_type(host, nombre='Reunión test', duracion=30):
    et, _ = EventType.objects.get_or_create(
        host=host,
        nombre=nombre,
        defaults={
            'descripcion': 'Event type para tests',
            'duracion_minutos': duracion,
            'buffer_antes_minutos': 0,
            'buffer_despues_minutos': 0,
            'aviso_minimo_minutos': 0,
            'activo': True,
        },
    )
    EventTypeXHost.objects.get_or_create(event_type=et, host=host)
    return et


def crear_disponibilidad(host, dia=0, inicio=time(9, 0), fin=time(18, 0)):
    bloque, _ = BloqueHorarioSemanal.objects.get_or_create(
        host=host,
        dia_semana=dia,
        hora_inicio=inicio,
        hora_fin=fin,
    )
    return bloque


def slot_futuro(dias=1, hora=10):
    """Devuelve un datetime UTC en el futuro que cae en día de semana."""
    base = datetime.now(timezone.utc).replace(hour=hora, minute=0, second=0, microsecond=0)
    candidato = base + timedelta(days=dias)
    # Ajusta al próximo lunes si cae en fin de semana
    while candidato.weekday() >= 5:
        candidato += timedelta(days=1)
    return candidato


def crear_reserva(event_type, inicio_utc=None):
    from calendario.bookings.services import crear_reserva as svc_crear
    if inicio_utc is None:
        inicio_utc = slot_futuro()
    return svc_crear(
        event_type=event_type,
        inicio_utc=inicio_utc,
        nombre_invitado=NOMBRE_INVITADO,
        email_invitado=EMAIL_INVITADO,
    )
