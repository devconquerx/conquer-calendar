import base64
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q, F


class Reserva(models.Model):

    class Estado(models.TextChoices):
        CONFIRMADA = 'confirmada', 'Confirmada'
        CANCELADA = 'cancelada', 'Cancelada'

    class GoogleSyncEstado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        SINCRONIZADO = 'sincronizado', 'Sincronizado'
        ERROR = 'error', 'Error'

    event_type = models.ForeignKey(
        'event_types.EventType',
        on_delete=models.PROTECT,
        related_name='reservas',
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reservas_recibidas',
    )
    inicio_utc = models.DateTimeField()
    fin_utc = models.DateTimeField()
    nombre_invitado = models.CharField(max_length=150)
    email_invitado = models.EmailField()
    telefono_invitado = models.CharField(max_length=50, blank=True, default='')
    notas = models.TextField(blank=True, default='')
    timezone_invitado = models.CharField(max_length=100, blank=True, default='')
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.CONFIRMADA,
    )
    confirmacion_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    google_event_id = models.CharField(max_length=200, blank=True, default='', db_index=True)
    google_meet_url = models.URLField(blank=True, default='')
    google_sync_estado = models.CharField(
        max_length=20,
        choices=GoogleSyncEstado.choices,
        default=GoogleSyncEstado.PENDIENTE,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reservas'
        ordering = ['-inicio_utc']
        verbose_name = 'reserva'
        verbose_name_plural = 'reservas'
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'inicio_utc'],
                condition=Q(estado='confirmada'),
                name='uq_reserva_host_inicio_confirmada',
            ),
            models.CheckConstraint(
                check=Q(fin_utc__gt=F('inicio_utc')),
                name='ck_reserva_fin_mayor_inicio',
            ),
        ]
        indexes = [
            models.Index(
                fields=['host', 'estado', 'inicio_utc'],
                name='ix_reserva_host_estado_inicio',
            ),
        ]

    @property
    def google_event_url(self):
        """URL directa al evento en Google Calendar del host."""
        if not self.google_event_id:
            return ''
        try:
            eid = base64.b64encode(
                f"{self.google_event_id} {self.host.email}".encode()
            ).decode().rstrip('=')
            return f"https://calendar.google.com/calendar/event?eid={eid}"
        except Exception:
            return ''

    def __str__(self):
        return f"{self.event_type.nombre} — {self.nombre_invitado} @ {self.inicio_utc:%Y-%m-%d %H:%M UTC}"
