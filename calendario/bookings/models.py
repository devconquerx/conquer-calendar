import base64
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q, F
from taggit.managers import TaggableManager


class DominioRemitente(models.Model):
    """Dominio verificado en Mailgun desde el que se envían correos.

    Existe para que cada academia envíe desde su propio dominio sin tocar
    código: el admin edita remitente y buzón de respuestas, y surte efecto
    en el siguiente envío.

    OJO con `region`: Mailgun tiene dos infraestructuras separadas (UE y
    EEUU) y un dominio vive solo en una. Enviar contra la región equivocada
    devuelve 404 "Unknown sender domain" aunque el dominio esté verificado.
    """

    class Region(models.TextChoices):
        EU = 'eu', 'Europa (api.eu.mailgun.net)'
        US = 'us', 'Estados Unidos (api.mailgun.net)'

    API_URLS = {
        Region.EU: 'https://api.eu.mailgun.net/v3',
        Region.US: 'https://api.mailgun.net/v3',
    }

    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre',
        help_text='Etiqueta para reconocerlo en el admin. Ej. Conquer Blocks.',
    )
    dominio = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Dominio',
        help_text='Dominio verificado en Mailgun. Ej. conquerblocks.com',
    )
    region = models.CharField(
        max_length=2,
        choices=Region.choices,
        default=Region.EU,
        verbose_name='Región de Mailgun',
        help_text='La región en la que está dado de alta el dominio. Si no coincide, el envío falla.',
    )
    from_email = models.CharField(
        max_length=255,
        verbose_name='Remitente (From)',
        help_text='Dirección desde la que sale el correo. Ej. Conquer Blocks <noreply@conquerblocks.com>',
    )
    reply_to = models.EmailField(
        blank=True,
        default='',
        verbose_name='Responder a (Reply-To)',
        help_text=(
            'Buzón real al que llegan las respuestas del destinatario. '
            'Déjalo vacío solo si nadie va a leer las respuestas.'
        ),
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Si se desactiva, las plantillas que lo usen vuelven al remitente por defecto de la app.',
    )

    class Meta:
        db_table = 'dominios_remitente'
        ordering = ['nombre']
        verbose_name = 'Dominio de envío'
        verbose_name_plural = 'Dominios de envío'

    def __str__(self):
        return f'{self.nombre} ({self.dominio})'

    @property
    def api_url(self):
        return self.API_URLS[self.region]


class PlantillaCorreo(models.Model):
    class Formato(models.TextChoices):
        HTML = 'html', 'HTML (con logo, colores y botones)'
        TEXTO = 'texto', 'Texto plano (sin HTML)'

    nombre = models.CharField(max_length=150)
    logo = models.FileField(upload_to='plantillas_correo/', blank=True, null=True)
    color_encabezado = models.CharField(max_length=7, default='#111827', verbose_name='Color del encabezado')
    texto_encabezado = models.CharField(max_length=200)
    cuerpo = models.TextField(
        help_text=(
            'Variables: {{nombre_invitado}}, {{email_invitado}}, {{nombre_host}}, '
            '{{nombre_evento}}, {{fecha_hora}}, {{duracion}}, {{google_meet_url}}, '
            '{{link_cancelar}}, {{link_reagendar}}, {{link_confirmar}}'
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
    dominio = models.ForeignKey(
        DominioRemitente,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='plantillas',
        verbose_name='Dominio de envío',
        help_text=(
            'Desde qué dominio sale este correo. Vacío = remitente por defecto '
            'de la app (el de siempre).'
        ),
    )
    formato = models.CharField(
        max_length=10,
        choices=Formato.choices,
        default=Formato.HTML,
        verbose_name='Formato del correo',
        help_text='En texto plano se envía solo el cuerpo, sin logo, colores ni botones.',
    )
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
    # Setter que generó el link directo de preagendamiento (pre_email del User
    # en el CRM, p.ej. "juan.perez"). Viaja como query param `setter` en la URL
    # de /agenda/.../ (lo genera el CRM, equivalente al utm_term=pre_email que
    # usaba Calendly) y se manda al CRM como campo separado — ya no hace falta
    # empaquetarlo en utm_term, esa era una limitación de Calendly que con
    # calendario propio no aplica.
    setter = models.CharField(max_length=140, blank=True, default='')
    utm_source = models.CharField(max_length=255, blank=True, default='')
    utm_campaign = models.CharField(max_length=255, blank=True, default='')
    utm_medium = models.CharField(max_length=255, blank=True, default='')
    utm_term = models.CharField(max_length=255, blank=True, default='')
    utm_content = models.CharField(max_length=255, blank=True, default='')
    utm_idcampaign = models.CharField(max_length=255, blank=True, default='')
    utm_adsetid = models.CharField(max_length=255, blank=True, default='')
    utm_adid = models.CharField(max_length=255, blank=True, default='')
    utm_form_variant = models.CharField(max_length=500, blank=True, default='')
    url = models.CharField(
        max_length=1500, blank=True, default='',
        verbose_name='URL de origen',
        help_text='window.location.href del visitante al momento de reservar.',
    )

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
    # Intentos fallidos de envío. Solo se marca `*_enviado` cuando el correo
    # sale de verdad; el contador acota los reintentos para que una dirección
    # rota no se reintente cada 5 minutos hasta que empiece la sesión.
    recordatorio_1_intentos = models.PositiveSmallIntegerField(default=0)
    recordatorio_2_intentos = models.PositiveSmallIntegerField(default=0)

    # Botón "Confirmar asistencia" de los correos. No cambia nada en Google
    # Calendar (el invitado ya entra como 'accepted'): es solo la señal de que
    # el invitado leyó el correo y dijo que va.
    asistencia_confirmada = models.BooleanField(default=False)
    asistencia_confirmada_en = models.DateTimeField(null=True, blank=True)

    # Reglas free/busy: cuando el evento de esta reserva en Google Calendar lleva
    # alguna de las palabras/emojis configuradas en el tipo de evento, el sync
    # marca este flag y la reserva deja de contar para la unicidad (host,
    # inicio_utc), permitiendo reservar encima (overbooking, como Calendly).
    # Default False -> los eventos normales mantienen la protección anti doble
    # booking intacta.
    permite_overbooking = models.BooleanField(default=False)

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
                condition=Q(estado='confirmada', permite_overbooking=False),
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


class CancelacionReserva(models.Model):
    """
    Quién canceló una reserva, desde dónde y cuándo.

    Existe porque el 20/08/2026 hubo una tanda de cancelaciones y no se pudo
    responder a "¿quién canceló esto?": los logs del contenedor se van en cada
    despliegue, y la reserva solo guarda el estado final. Los closers no entran
    a la app —solo ven Google Calendar y sus correos—, así que cuando una
    reserva suya desaparece necesitan una respuesta mejor que "lo hizo el
    sistema".

    Va en una tabla aparte y no en campos de `Reserva` para no engordar la tabla
    más consultada de la app, y para que el histórico se conserve aunque la
    reserva se reagende después.
    """

    class Origen(models.TextChoices):
        PANEL = 'panel', 'Panel interno'
        PUBLICA = 'publica', 'El invitado, desde su enlace'
        SYNC_GCAL = 'sync_gcal', 'Rechazo del host en Google Calendar'
        COMANDO = 'comando', 'Comando de mantenimiento'
        REAGENDADA = 'reagendada', 'Reagendada (se movió a otra hora)'
        DESCONOCIDO = 'desconocido', 'Sin identificar'

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        related_name='cancelaciones',
    )
    origen = models.CharField(
        max_length=20,
        choices=Origen.choices,
        default=Origen.DESCONOCIDO,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cancelaciones_hechas',
        help_text='Quién la canceló, cuando se sabe (panel o comando).',
    )
    detalle = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Email del host que rechazó, del invitado que canceló, etc.',
    )
    correo_enviado = models.BooleanField(
        default=False,
        help_text='Si se avisó al invitado por Google al cancelar.',
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cancelaciones_reserva'
        verbose_name = 'cancelación de reserva'
        verbose_name_plural = 'cancelaciones de reservas'
        ordering = ['-creada_en']
        indexes = [
            models.Index(fields=['-creada_en'], name='ix_cancelacion_fecha'),
            models.Index(fields=['origen'], name='ix_cancelacion_origen'),
        ]

    def __str__(self):
        return f'{self.reserva_id} — {self.get_origen_display()} ({self.creada_en:%Y-%m-%d %H:%M})'
