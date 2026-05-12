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
    buffer_antes_minutos = models.PositiveSmallIntegerField(default=0)
    buffer_despues_minutos = models.PositiveSmallIntegerField(default=0)
    aviso_minimo_horas = models.PositiveSmallIntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    activo = models.BooleanField(default=True)
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

    def __str__(self):
        return f"{self.nombre} ({self.duracion_minutos} min)"


class EventTypeXHost(models.Model):
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
    fecha_creacion = models.DateTimeField(auto_now_add=True)

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
