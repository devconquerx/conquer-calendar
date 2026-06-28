from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone as django_tz


class GoogleCalendarEvento(models.Model):
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eventos_gcal',
    )
    google_event_id = models.CharField(max_length=1024)
    titulo = models.CharField(
        max_length=1024,
        blank=True,
        default='',
        help_text="Título (summary) del evento en Google Calendar. Se usa para "
                  "las reglas free/busy por palabra/emoji del tipo de evento.",
    )
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


class GoogleCalendarSyncLog(models.Model):
    SYNC_INICIAL = 'sync_inicial'
    SYNC_INCREMENTAL = 'sync_incremental'
    WATCH_GCAL = 'watch_gcal'
    RENOVAR_CANALES = 'renovar_canales'

    COMANDO_CHOICES = [
        (SYNC_INICIAL, 'sync_gcal_inicial'),
        (SYNC_INCREMENTAL, 'sync_gcal_incremental'),
        (WATCH_GCAL, 'watch_gcal'),
        (RENOVAR_CANALES, 'renovar_canales_gcal'),
    ]

    comando = models.CharField(max_length=30, choices=COMANDO_CHOICES)
    ejecutado_en = models.DateTimeField(auto_now_add=True)
    total = models.PositiveIntegerField(default=0)
    exitosos = models.PositiveIntegerField(default=0)
    fallidos = models.PositiveIntegerField(default=0)
    hosts_fallidos = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'google_calendar_sync_log'
        ordering = ['-ejecutado_en']
        verbose_name = 'log de sync'
        verbose_name_plural = 'logs de sync'
        indexes = [
            models.Index(fields=['ejecutado_en'], name='ix_gcal_log_ejecutado'),
            models.Index(fields=['comando'], name='ix_gcal_log_comando'),
        ]

    def __str__(self):
        return f"{self.get_comando_display()} {self.ejecutado_en:%Y-%m-%d %H:%M} — {self.exitosos}/{self.total} OK"

    @classmethod
    def registrar(cls, comando, total, exitosos, fallidos_emails):
        cls.objects.create(
            comando=comando,
            total=total,
            exitosos=exitosos,
            fallidos=len(fallidos_emails),
            hosts_fallidos=', '.join(fallidos_emails),
        )
        corte = django_tz.now() - timedelta(days=90)
        cls.objects.filter(ejecutado_en__lt=corte).delete()
