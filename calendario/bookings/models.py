import base64
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q, F
from taggit.managers import TaggableManager


class PlantillaCorreo(models.Model):
    nombre = models.CharField(max_length=150)
    logo = models.FileField(upload_to='plantillas_correo/', blank=True, null=True)
    color_encabezado = models.CharField(max_length=7, default='#111827', verbose_name='Color del encabezado')
    texto_encabezado = models.CharField(max_length=200)
    cuerpo = models.TextField(
        help_text=(
            'Variables: {{nombre_invitado}}, {{email_invitado}}, {{nombre_host}}, '
            '{{nombre_evento}}, {{fecha_hora}}, {{duracion}}, {{google_meet_url}}, {{link_cancelar}}'
        )
    )
    pie_pagina = models.CharField(max_length=300, blank=True, default='')
    campos_visibles = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Campos visibles en el correo',
    )
    recordatorio_1_activo = models.BooleanField(default=True, verbose_name='Recordatorio 1 activo')
    recordatorio_1_horas = models.PositiveSmallIntegerField(default=24, verbose_name='Recordatorio 1 — horas antes')
    recordatorio_2_activo = models.BooleanField(default=False, verbose_name='Recordatorio 2 activo')
    recordatorio_2_horas = models.PositiveSmallIntegerField(default=1, verbose_name='Recordatorio 2 — horas antes')
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'plantillas_correo'
        verbose_name = 'Plantilla de correo'
        verbose_name_plural = 'Plantillas de correo'

    def __str__(self):
        return self.nombre


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

    # Tracking: snapshot al crear la reserva (del tracking de la Prellamada en el
    # flujo del funnel). Queda autocontenido en la reserva y se envía al CRM
    # schedule y al respaldo de Supabase sin depender del Lead/Prellamada
    # enlazados. Vacío en reservas creadas fuera del funnel (calendario directo).
    journey_id = models.CharField(max_length=120, blank=True, default='', db_index=True)
    event_id = models.CharField(max_length=120, blank=True, default='')
    utm_source = models.CharField(max_length=255, blank=True, default='')
    utm_campaign = models.CharField(max_length=255, blank=True, default='')
    utm_medium = models.CharField(max_length=255, blank=True, default='')
    utm_term = models.CharField(max_length=255, blank=True, default='')
    utm_content = models.CharField(max_length=255, blank=True, default='')
    utm_idcampaign = models.CharField(max_length=255, blank=True, default='')
    utm_adsetid = models.CharField(max_length=255, blank=True, default='')
    utm_adid = models.CharField(max_length=255, blank=True, default='')
    utm_form_variant = models.CharField(max_length=500, blank=True, default='')

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
    recordatorio_1_enviado = models.BooleanField(default=False)
    recordatorio_2_enviado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    # Tags de estado para las tareas de conversión (browser_done, sch_*_done, *_failed)
    tags = TaggableManager(blank=True)

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


class ConfigCorreoEvento(models.Model):
    event_type = models.OneToOneField(
        'event_types.EventType',
        on_delete=models.CASCADE,
        related_name='config_correo',
    )
    plantilla_confirmacion_host = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='configs_confirmacion_host',
        verbose_name='Correo al host',
        help_text='Si no se selecciona, Google Calendar solo notifica al host si el invitado confirma manualmente.',
    )
    plantilla_confirmacion_inv = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='configs_confirmacion_inv',
        verbose_name='Correo al invitado',
        help_text='Si no se selecciona, Google Calendar sigue enviando su correo por defecto.',
    )
    plantilla_recordatorio = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='configs_recordatorio_evento',
        verbose_name='Plantilla de recordatorio',
        help_text='Los tiempos de envío se leen de la plantilla seleccionada.',
    )

    class Meta:
        db_table = 'config_correo_evento'
        verbose_name = 'Configuración de correo por evento'
        verbose_name_plural = 'Configuraciones de correo por evento'

    def __str__(self):
        return f'Config correo — {self.event_type.nombre}'


class ConfigCorreoDefault(models.Model):
    """Config global de correos — aplica a todos cuando no hay config por evento ni grupo."""
    plantilla_confirmacion_host = models.ForeignKey(
        PlantillaCorreo, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='default_confirmacion_host',
        verbose_name='Correo al host (por defecto)',
    )
    plantilla_confirmacion_inv = models.ForeignKey(
        PlantillaCorreo, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='default_confirmacion_inv',
        verbose_name='Correo al invitado (por defecto)',
    )
    plantilla_recordatorio = models.ForeignKey(
        PlantillaCorreo, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='default_recordatorio',
        verbose_name='Recordatorio (por defecto)',
    )

    class Meta:
        db_table = 'config_correo_default'
        verbose_name = 'Configuración global de correos'
        verbose_name_plural = 'Configuración global de correos'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Configuración global de correos'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ConfigCorreoGrupo(models.Model):
    grupo = models.OneToOneField(
        'grupos.Grupo',
        on_delete=models.CASCADE,
        related_name='config_correo',
    )
    plantilla_confirmacion_host = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='configs_grupo_confirmacion_host',
        verbose_name='Correo al host',
        help_text='Se aplica a todos los miembros del grupo salvo que el evento tenga su propia config. Sin plantilla, Google Calendar solo notifica al host si el invitado confirma manualmente.',
    )
    plantilla_confirmacion_inv = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='configs_grupo_confirmacion_inv',
        verbose_name='Correo al invitado',
    )
    plantilla_recordatorio = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='configs_grupo_recordatorio',
        verbose_name='Plantilla de recordatorio',
    )

    class Meta:
        db_table = 'config_correo_grupo'
        verbose_name = 'Configuración de correo por grupo'
        verbose_name_plural = 'Configuraciones de correo por grupo'

    def __str__(self):
        return f'Config correo — {self.grupo.nombre}'


class ConfigCorreoMiembroGrupo(models.Model):
    """Config de correo por miembro dentro de un grupo — sobreescribe la config del grupo para ese usuario."""
    grupo = models.ForeignKey(
        'grupos.Grupo',
        on_delete=models.CASCADE,
        related_name='configs_correo_miembro',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='configs_correo_grupo',
    )
    plantilla_confirmacion_host = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Correo al host',
    )
    plantilla_confirmacion_inv = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Correo al invitado',
    )
    plantilla_recordatorio = models.ForeignKey(
        PlantillaCorreo,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Plantilla de recordatorio',
    )

    class Meta:
        db_table = 'config_correo_miembro_grupo'
        unique_together = [('grupo', 'usuario')]
        verbose_name = 'Configuración de correo por miembro'
        verbose_name_plural = 'Configuraciones de correo por miembro'

    def __str__(self):
        return f'Config correo — {self.usuario} en {self.grupo.nombre}'


class LogCorreo(models.Model):
    class Tipo(models.TextChoices):
        CONFIRMACION_HOST = 'confirmacion_host', 'Confirmación host'
        CONFIRMACION_INV = 'confirmacion_inv', 'Confirmación invitado'
        RECORDATORIO_1 = 'recordatorio_1', 'Recordatorio 1'
        RECORDATORIO_2 = 'recordatorio_2', 'Recordatorio 2'
        CANCELACION = 'cancelacion', 'Cancelación'

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        related_name='logs_correo',
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    plantilla = models.ForeignKey(
        PlantillaCorreo,
        null=True,
        on_delete=models.SET_NULL,
        related_name='logs',
    )
    destinatario = models.EmailField()
    enviado_en = models.DateTimeField(auto_now_add=True)
    exitoso = models.BooleanField()
    error_detalle = models.TextField(blank=True, default='')
    html_content = models.TextField(blank=True, default='', verbose_name='Contenido HTML')
    payload = models.JSONField(default=dict, blank=True, verbose_name='Payload')

    class Meta:
        db_table = 'logs_correo'
        verbose_name = 'Log de correo'
        verbose_name_plural = 'Logs de correo'
        ordering = ['-enviado_en']

    def __str__(self):
        return f'{self.tipo} → {self.destinatario} ({self.enviado_en:%Y-%m-%d %H:%M})'
