import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class EventType(models.Model):
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_types',
    )
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=120)
    descripcion = models.TextField(blank=True, default='')
    duracion_minutos = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(480)],
    )
    AVISO_MINIMO_CHOICES = [
        (0,   'Sin aviso mínimo'),
        (15,  '15 minutos'),
        (30,  '30 minutos'),
        (45,  '45 minutos'),
        (60,  '1 hora'),
        (120, '2 horas'),
        (180, '3 horas'),
        (1440,  '1 día'),
        (4320,  '3 días'),
        (14400, '10 días'),
    ]

    INCREMENTO_CHOICES = [
        (15, '15 minutos'),
        (20, '20 minutos'),
        (30, '30 minutos'),
        (40, '40 minutos'),
        (45, '45 minutos'),
        (60, '60 minutos'),
    ]
    incremento_inicio_minutos = models.PositiveSmallIntegerField(
        default=30,
        choices=INCREMENTO_CHOICES,
        help_text="Cada cuántos minutos aparece un slot disponible.",
    )
    buffer_antes_minutos = models.PositiveSmallIntegerField(default=0)
    buffer_despues_minutos = models.PositiveSmallIntegerField(default=0)
    aviso_minimo_minutos = models.PositiveSmallIntegerField(
        default=0,
        choices=AVISO_MINIMO_CHOICES,
    )
    aviso_maximo_dias = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Rango máximo (rolling) en días contados al minuto desde el momento actual.",
    )
    # Hasta dónde se puede reservar. Dos modos excluyentes, como en Calendly:
    #   'rolling' -> los próximos N días desde ahora mismo (aviso_maximo_dias);
    #   'fechas'  -> un rango fijo con fecha de inicio y de fin, para eventos que
    #                solo existen en una temporada concreta (una convocatoria, un
    #                curso) y que dejan de aceptar reservas al pasarse.
    # El modo por defecto es el rolling: los eventos que ya existen no cambian.
    RANGO_ROLLING = 'rolling'
    RANGO_FECHAS = 'fechas'
    RANGO_CHOICES = [
        (RANGO_ROLLING, 'Días rodantes (a partir de hoy)'),
        (RANGO_FECHAS, 'Rango de fechas concreto'),
    ]
    rango_tipo = models.CharField(
        max_length=10,
        choices=RANGO_CHOICES,
        default=RANGO_ROLLING,
        verbose_name='Tipo de rango de reserva',
    )
    rango_fecha_inicio = models.DateField(
        null=True, blank=True,
        verbose_name='Reservable desde',
        help_text="Solo se usa con el rango de fechas concreto.",
    )
    rango_fecha_fin = models.DateField(
        null=True, blank=True,
        verbose_name='Reservable hasta',
        help_text="Solo se usa con el rango de fechas concreto. Es un día inclusive.",
    )
    FORMATO_TITULO_CHOICES = [
        ('evento_invitado', 'Evento · Invitado  (ej: "Consultoría con Juan")'),
        ('invitado_evento', 'Invitado · Evento  (ej: "Juan - Consultoría")'),
    ]
    formato_titulo_gcal = models.CharField(
        max_length=20,
        choices=FORMATO_TITULO_CHOICES,
        default='evento_invitado',
        help_text="Orden del título que aparece en Google Calendar / Google Meet.",
    )
    slug_equipo = models.SlugField(max_length=120, blank=True, null=True, unique=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class CrmDestino(models.TextChoices):
        NO_ENVIAR = 'none', 'No enviar al CRM'
        ONBOARDING = 'onboarding', 'Onboarding'
        SCHEDULE = 'schedule', 'Schedule (llamada)'

    crm_destino = models.CharField(
        max_length=20,
        choices=CrmDestino.choices,
        default=CrmDestino.NO_ENVIAR,
        verbose_name='Destino en el CRM',
        help_text=(
            "A qué tabla del CRM se envía la reserva al agendarse: 'No enviar' "
            "(default, no va al CRM), 'Onboarding', o 'Schedule' (la llamada de venta; "
            "además dispara las conversiones a redes/ActiveCampaign/Respond.io)."
        ),
    )

    class ConfirmacionTipo(models.TextChoices):
        DEFAULT = 'default', 'Página de confirmación'
        URL = 'url', 'URL personalizada'

    confirmacion_tipo = models.CharField(
        max_length=10,
        choices=ConfirmacionTipo.choices,
        default=ConfirmacionTipo.DEFAULT,
        verbose_name='Redirección post-reserva',
        help_text='A dónde se lleva al invitado después de reservar.',
    )
    confirmacion_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='Path de confirmación',
        help_text='Path interno (ej: /conquer-blocks/confirmacion-llamada-latam/). Solo aplica si el tipo es "URL personalizada".',
    )

    unico_por_invitado = models.BooleanField(
        default=True,
        help_text="Si está activo, un mismo email no puede reservar este evento dos veces mientras tenga una reserva futura confirmada.",
    )

    gcal_palabras_ignorar = models.TextField(
        blank=True,
        default='',
        verbose_name='Palabras/emojis que liberan el horario',
        help_text=(
            "Reglas free/busy: si un evento de Google Calendar contiene alguna de "
            "estas palabras o emojis en su título, NO bloqueará los horarios (se "
            "podrá agendar encima). Una por línea. Si se le quita la palabra al "
            "evento en Google Calendar, vuelve a bloquear. Solo aplica a hosts con "
            "sincronización de calendario activa."
        ),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'event_types'
        ordering = ['host_id', 'nombre']
        verbose_name = 'tipo de evento'
        verbose_name_plural = 'tipos de evento'
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'nombre'],
                name='uq_event_type_host_nombre',
            ),
            models.UniqueConstraint(
                fields=['host', 'slug'],
                name='uq_event_type_host_slug',
            ),
        ]
        indexes = [
            models.Index(fields=['host', 'activo'], name='ix_event_type_host_activo'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre) or 'evento'
            self.slug = base
            i = 2
            while EventType.objects.exclude(pk=self.pk).filter(host=self.host, slug=self.slug).exists():
                self.slug = f'{base}-{i}'
                i += 1
        super().save(*args, **kwargs)

    def clean(self):
        if self.precio is not None and self.precio < 0:
            raise ValidationError({'precio': 'El precio no puede ser negativo.'})
        if self.rango_tipo == self.RANGO_FECHAS:
            errores = {}
            if not self.rango_fecha_inicio:
                errores['rango_fecha_inicio'] = 'Indica desde qué día se puede reservar.'
            if not self.rango_fecha_fin:
                errores['rango_fecha_fin'] = 'Indica hasta qué día se puede reservar.'
            if (self.rango_fecha_inicio and self.rango_fecha_fin
                    and self.rango_fecha_fin < self.rango_fecha_inicio):
                errores['rango_fecha_fin'] = 'La fecha final no puede ser anterior a la inicial.'
            if errores:
                raise ValidationError(errores)

    @property
    def usa_rango_de_fechas(self):
        """El evento está limitado a un rango fijo y lo tiene bien configurado.

        Las dos fechas son obligatorias en ese modo (lo valida `clean`), pero se
        comprueban igual: un objeto construido a mano o una fila vieja no deben
        acabar en una ventana a medias.
        """
        return (self.rango_tipo == self.RANGO_FECHAS
                and self.rango_fecha_inicio is not None
                and self.rango_fecha_fin is not None)

    def ventana_reservas(self, hoy_local):
        """Primer y último día reservables (ambos inclusive), en fechas locales.

        Único sitio donde se decide la ventana: lo usan tanto el cálculo de slots
        como las vistas públicas, para que el calendario no ofrezca días que
        después se rechazarían al reservar.

        Con el rango fijo el pasado se recorta igual (no se reserva ayer aunque el
        rango empiece antes), y si el rango ya terminó devuelve una ventana vacía
        —el último día cae antes que el primero—, que los consumidores traducen a
        "no hay horas".
        """
        if self.usa_rango_de_fechas:
            return max(hoy_local, self.rango_fecha_inicio), self.rango_fecha_fin
        return hoy_local, hoy_local + timedelta(days=self.aviso_maximo_dias)

    @property
    def gcal_palabras_ignorar_lista(self):
        """Lista normalizada de palabras/emojis que liberan el horario.

        Cada línea es una regla independiente. Se ignoran líneas vacías. El
        match contra el título del evento es 'includes' (substring) e
        insensible a mayúsculas; ver `titulo_libera_horario` en services.
        """
        return [
            linea.strip()
            for linea in (self.gcal_palabras_ignorar or '').splitlines()
            if linea.strip()
        ]

    def __str__(self):
        return f"{self.nombre} ({self.duracion_minutos} min)"


class EventTypeXHost(models.Model):
    # Prioridad en el reparto round-robin. Rango cerrado 0..3, donde 0 es el valor
    # centinela «excluido»: el organizador sigue en el pool y en el formulario, pero
    # no recibe reservas ni aporta sus horas a los slots que se ofrecen, hasta que
    # se le vuelva a poner un número >= 1.
    # De 1 a 3 es prioridad real: todos los organizadores nacen en PRIORIDAD_DEFECTO,
    # así que mientras nadie la toque el criterio es constante y no desempata nada
    # (el reparto se comporta exactamente igual que antes de existir este campo).
    PRIORIDAD_EXCLUIDO = 0
    PRIORIDAD_MIN = 0
    PRIORIDAD_MAX = 3
    PRIORIDAD_DEFECTO = 1

    event_type = models.ForeignKey(
        EventType,
        on_delete=models.CASCADE,
        related_name='hosts_pool',
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_types_round_robin',
    )
    prioridad = models.PositiveSmallIntegerField(
        default=PRIORIDAD_DEFECTO,
        validators=[
            MinValueValidator(PRIORIDAD_MIN),
            MaxValueValidator(PRIORIDAD_MAX),
        ],
        verbose_name='Prioridad en el round-robin',
        help_text=(
            "De 1 a 3, donde 3 es la más alta. Cuando varios organizadores están "
            "libres a la misma hora, la reserva se asigna al de mayor prioridad; a "
            "igualdad de prioridad decide el reparto de carga de siempre. "
            "0 lo deja fuera de este evento: no recibe reservas ni ofrece sus horas "
            "hasta que se le ponga un número mayor que 0."
        ),
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def excluido(self):
        """El organizador está en el pool pero apartado del reparto (prioridad 0)."""
        return self.prioridad == self.PRIORIDAD_EXCLUIDO

    class Meta:
        db_table = 'event_types_x_hosts'
        ordering = ['event_type_id', 'id']
        verbose_name = 'host de round-robin'
        verbose_name_plural = 'hosts de round-robin'
        constraints = [
            models.UniqueConstraint(
                fields=['event_type', 'host'],
                name='uq_etxh_event_type_host',
            ),
        ]
        indexes = [
            models.Index(fields=['event_type'], name='ix_etxh_event_type'),
            models.Index(fields=['host'], name='ix_etxh_host'),
        ]

    def __str__(self):
        return f"{self.event_type.nombre} ↔ {self.host.username}"


class DisponibilidadEtxh(models.Model):
    DIAS = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
    ]
    etxh = models.ForeignKey(
        EventTypeXHost,
        on_delete=models.CASCADE,
        related_name='disponibilidad',
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        db_table = 'disponibilidad_etxh'
        ordering = ['dia_semana', 'hora_inicio']

    def __str__(self):
        return f"{self.etxh} · {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"


class DisponibilidadFechaEtxh(models.Model):
    etxh = models.ForeignKey(
        EventTypeXHost,
        on_delete=models.CASCADE,
        related_name='disponibilidad_fechas',
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = 'disponibilidad_fecha_etxh'
        ordering = ['fecha', 'hora_inicio']

    def __str__(self):
        rango = f"{self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}" if self.hora_inicio else "Cerrado"
        return f"{self.etxh} · {self.fecha} {rango}"


class EnlaceUnico(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.CASCADE,
        related_name='enlaces_unicos',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enlaces_unicos_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)
    usado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'event_type_enlaces_unicos'
        ordering = ['-creado_en']
        verbose_name = 'enlace único'
        verbose_name_plural = 'enlaces únicos'
        indexes = [
            models.Index(fields=['token'], name='ix_enlace_unico_token'),
        ]

    def __str__(self):
        return f"EnlaceUnico({self.token}) → {self.event_type.nombre}"
