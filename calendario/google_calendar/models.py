from django.conf import settings
from django.db import models
from django.db.models import F, Q


class GoogleCalendarEvento(models.Model):
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eventos_gcal',
    )
    google_event_id = models.CharField(max_length=1024)
    inicio_utc = models.DateTimeField()
    fin_utc = models.DateTimeField()
    es_todo_el_dia = models.BooleanField(default=False)
    transparencia = models.CharField(max_length=20, default='opaque')
    estado = models.CharField(max_length=20, default='confirmed')
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'google_calendar_eventos'
        ordering = ['host_id', 'inicio_utc']
        verbose_name = 'evento de Google Calendar'
        verbose_name_plural = 'eventos de Google Calendar'
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'google_event_id'],
                name='uq_gcal_evento_host_event',
            ),
            models.CheckConstraint(
                check=Q(fin_utc__gt=F('inicio_utc')),
                name='ck_gcal_evento_fin_mayor_inicio',
            ),
        ]
        indexes = [
            models.Index(
                fields=['host', 'inicio_utc', 'fin_utc'],
                name='ix_gcal_evento_host_rango',
            ),
        ]

    def __str__(self):
        return f"{self.host} {self.inicio_utc:%Y-%m-%d %H:%M}–{self.fin_utc:%H:%M}"


class GoogleCalendarSyncEstado(models.Model):
    SIN_SINCRONIZAR = 'sin_sincronizar'
    ACTIVO = 'activo'
    ERROR = 'error'

    ESTADO_CHOICES = [
        (SIN_SINCRONIZAR, 'Sin sincronizar'),
        (ACTIVO, 'Activo'),
        (ERROR, 'Error'),
    ]

    host = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gcal_sync',
    )
    sync_token = models.TextField(blank=True, default='')
    canal_id = models.CharField(max_length=200, blank=True, default='')
    canal_resource_id = models.CharField(max_length=200, blank=True, default='')
    canal_expira_utc = models.DateTimeField(null=True, blank=True)
    ultima_sync_utc = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=SIN_SINCRONIZAR,
    )

    class Meta:
        db_table = 'google_calendar_sync_estado'
        verbose_name = 'estado de sync de Google Calendar'
        verbose_name_plural = 'estados de sync de Google Calendar'
        indexes = [
            models.Index(
                fields=['canal_expira_utc'],
                name='ix_gcal_sync_expira',
            ),
        ]

    def __str__(self):
        return f"{self.host} [{self.estado}]"
