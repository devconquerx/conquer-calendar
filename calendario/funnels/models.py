import uuid

from django.db import models


class FunnelForm(models.Model):
    """Un formulario de prellamada por escuela+región.

    `config` (JSONField) guarda los bloques del formulario, su orden, las
    validaciones de scoring (validate / neverCancel), los rangos de
    score→evento, la pantalla de rechazo y settings/theme/messages.
    Réplica de cada `formXxx` de `funnels-new/src/data/formObj.jsx`.
    """

    key = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Clave',
        help_text='Réplica del `key` de formObj. Ej. FullLatam.',
    )
    slug = models.SlugField(
        max_length=80,
        unique=True,
        verbose_name='Slug',
        help_text='Identificador interno del funnel (usado en la API /f/api/<slug>/).',
    )
    escuela = models.CharField(
        max_length=40,
        verbose_name='Escuela',
        help_text='Ej. conquer-blocks, conquer-finance, conquer-languages, conquer-legal.',
    )
    region = models.CharField(
        max_length=10,
        verbose_name='Región',
        help_text='latam / eu / us.',
    )
    nombre = models.CharField(max_length=120, verbose_name='Nombre')
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Configuración (JSON)',
        help_text=(
            'blocks, q_order, validate, neverCancel, score_ranges, '
            'cancel_screen, settings, theme, messages.'
        ),
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'funnel_forms'
        ordering = ['escuela', 'region']
        verbose_name = 'formulario de funnel'
        verbose_name_plural = 'formularios de funnel'

    def __str__(self):
        return f'{self.nombre} ({self.escuela}/{self.region})'


class FunnelScoring(models.Model):
    """Tabla global de puntuaciones (singleton, pk=1).

    Réplica del array `scores` de `funnels-new/src/data/scores.jsx`. Se
    mantiene como singleton compartido por todos los `FunnelForm` para no
    duplicar la tabla de países (~200 entradas) en cada formulario.
    """

    config = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Tabla de puntuaciones (JSON)',
        help_text='Array de scores (réplica de scores.jsx).',
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'funnel_scoring'
        verbose_name = 'tabla de puntuaciones'
        verbose_name_plural = 'tabla de puntuaciones'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return 'Tabla de puntuaciones (global)'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Prellamada(models.Model):
    """Cada submission del formulario de prellamada.

    Guarda datos del lead, respuestas, score, evento asignado y, si el
    visitante llega a agendar, FK a la `Reserva` resultante. Si abandona en
    el calendario, queda guardada sin `reserva` (lead capturado igual).
    """

    class Resultado(models.TextChoices):
        CALENDARIO = 'calendario', 'Calendario'
        RECHAZADO = 'rechazado', 'Rechazado'

    funnel = models.ForeignKey(
        'funnels.FunnelForm',
        on_delete=models.PROTECT,
        related_name='prellamadas',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nombre = models.CharField(max_length=160)
    email = models.EmailField()
    telefono = models.CharField(max_length=40, blank=True, default='')
    respuestas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Respuestas',
        help_text='dict {campo: valor} de todas las respuestas.',
    )
    score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    event_type = models.ForeignKey(
        'event_types.EventType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='prellamadas',
    )
    reserva = models.OneToOneField(
        'bookings.Reserva',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='prellamada',
    )
    tracking = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Tracking',
        help_text='UTM/journey opcional, sin lógica MVP.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'prellamadas'
        ordering = ['-creado_en']
        verbose_name = 'prellamada'
        verbose_name_plural = 'prellamadas'
        indexes = [
            models.Index(fields=['funnel', 'creado_en'], name='ix_prellamada_funnel_creado'),
            models.Index(fields=['resultado'], name='ix_prellamada_resultado'),
        ]

    def __str__(self):
        return f'{self.nombre} <{self.email}> — {self.resultado} ({self.creado_en:%Y-%m-%d %H:%M})'
