from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F


class Horario(models.Model):
    """
    Un juego de horarios con nombre ("Default", "Horario USA").

    Cada host tiene los suyos —no se comparten entre personas— y exactamente uno
    marcado como default. Los tipos de evento pueden apuntar a uno concreto
    (`EventTypeXHost.horario`); el que no apunta a ninguno usa el default, que es
    justo el comportamiento que había antes de que existieran los horarios.
    """

    NOMBRE_DEFAULT = 'Default'

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='horarios',
    )
    nombre = models.CharField(max_length=80)
    es_default = models.BooleanField(
        default=False,
        verbose_name='Es el horario por defecto',
        help_text=(
            'El que usan los tipos de evento que no tienen uno asignado. '
            'Solo puede haber uno por persona y no se puede borrar.'
        ),
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'horarios'
        ordering = ['host_id', '-es_default', 'nombre']
        verbose_name = 'horario'
        verbose_name_plural = 'horarios'
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'nombre'],
                name='uq_horario_host_nombre',
            ),
            # Un único default por persona. La condición deja pasar tantos
            # no-default como haga falta.
            models.UniqueConstraint(
                fields=['host'],
                condition=Q(es_default=True),
                name='uq_horario_un_default_por_host',
            ),
        ]
        indexes = [
            models.Index(fields=['host'], name='ix_horario_host'),
        ]

    def __str__(self):
        return f"{self.host.username} · {self.nombre}"

    @property
    def en_uso_por(self):
        """Tipos de evento que apuntan expresamente a este horario."""
        from calendario.event_types.models import EventTypeXHost
        return EventTypeXHost.objects.filter(horario=self).select_related('event_type')


class BloqueHorarioSemanal(models.Model):

    class DiaSemana(models.IntegerChoices):
        LUNES = 0, 'Lunes'
        MARTES = 1, 'Martes'
        MIERCOLES = 2, 'Miércoles'
        JUEVES = 3, 'Jueves'
        VIERNES = 4, 'Viernes'
        SABADO = 5, 'Sábado'
        DOMINGO = 6, 'Domingo'

    horario = models.ForeignKey(
        Horario,
        on_delete=models.CASCADE,
        related_name='bloques_semanales',
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bloques_horarios_semanales'
        ordering = ['horario_id', 'dia_semana', 'hora_inicio']
        verbose_name = 'bloque horario semanal'
        verbose_name_plural = 'bloques horarios semanales'
        indexes = [
            models.Index(fields=['horario', 'dia_semana'], name='ix_bloque_horario_dia'),
        ]
        constraints = [
            # Único dentro del horario, no dentro de la persona: la misma
            # persona puede tener 9–17 en su Default y en su Horario USA.
            models.UniqueConstraint(
                fields=['horario', 'dia_semana', 'hora_inicio', 'hora_fin'],
                name='uq_bloque_horario_dia_rango',
            ),
            models.CheckConstraint(
                check=Q(hora_fin__gt=F('hora_inicio')),
                name='ck_bloque_hora_fin_mayor_inicio',
            ),
        ]

    def clean(self):
        if self.hora_fin and self.hora_inicio and self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la de inicio.'})
        if self.horario_id is None:
            return
        qs = BloqueHorarioSemanal.objects.filter(
            horario_id=self.horario_id, dia_semana=self.dia_semana
        ).exclude(pk=self.pk)
        if qs.filter(hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio).exists():
            raise ValidationError('Este bloque se solapa con otro existente del mismo día.')

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"


class BloqueHorarioFecha(models.Model):
    """
    Horario específico para una fecha concreta. Cuando una fecha tiene al menos
    un bloque, estos rangos SOBRESCRIBEN al horario semanal de ese día (igual
    que el "date-specific hours" de Calendly).

    Una fila **sin horas** (las dos a `None`) significa día cerrado: ese día no
    tiene huecos por mucho que el horario semanal diga otra cosa. Es la forma de
    tapar un festivo sin tocar la semana entera.
    """

    horario = models.ForeignKey(
        Horario,
        on_delete=models.CASCADE,
        related_name='bloques_fecha',
    )
    fecha = models.DateField()
    # Las dos a None = día cerrado. El CheckConstraint de abajo se satisface
    # solo con nulls (en SQL una comparación con NULL no es falsa, es NULL).
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    @property
    def cerrado(self):
        return self.hora_inicio is None and self.hora_fin is None

    class Meta:
        db_table = 'bloques_horarios_fecha'
        ordering = ['horario_id', 'fecha', 'hora_inicio']
        verbose_name = 'bloque horario por fecha'
        verbose_name_plural = 'bloques horarios por fecha'
        indexes = [
            models.Index(fields=['horario', 'fecha'], name='ix_bloque_horario_fecha'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['horario', 'fecha', 'hora_inicio', 'hora_fin'],
                name='uq_bloque_horario_fecha_rango',
            ),
            # Un día cerrado es único de por sí: con las horas a NULL el unique
            # de arriba no aplica (en SQL NULL nunca iguala a NULL).
            models.UniqueConstraint(
                fields=['horario', 'fecha'],
                condition=Q(hora_inicio__isnull=True),
                name='uq_bloque_horario_fecha_cerrado',
            ),
            models.CheckConstraint(
                check=Q(hora_fin__gt=F('hora_inicio')),
                name='ck_bloque_fecha_hora_fin_mayor_inicio',
            ),
            # Las dos horas van juntas: o hay rango, o es día cerrado. Media fila
            # (solo inicio, solo fin) no significa nada.
            models.CheckConstraint(
                check=(
                    Q(hora_inicio__isnull=False, hora_fin__isnull=False)
                    | Q(hora_inicio__isnull=True, hora_fin__isnull=True)
                ),
                name='ck_bloque_fecha_horas_completas',
            ),
        ]

    def clean(self):
        if (self.hora_inicio is None) != (self.hora_fin is None):
            raise ValidationError('Pon las dos horas, o ninguna para cerrar el día.')
        if self.hora_fin and self.hora_inicio and self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la de inicio.'})
        if self.horario_id is None:
            return
        qs = BloqueHorarioFecha.objects.filter(
            horario_id=self.horario_id, fecha=self.fecha
        ).exclude(pk=self.pk)
        if self.cerrado:
            # Cerrar un día que ya tiene rangos (o al revés) es contradictorio.
            if qs.exists():
                raise ValidationError('Esta fecha ya tiene horarios; quítalos antes de cerrarla.')
            return
        if qs.filter(hora_inicio__isnull=True).exists():
            raise ValidationError('Esta fecha está marcada como cerrada; ábrela antes de darle horas.')
        if qs.filter(hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio).exists():
            raise ValidationError('Este bloque se solapa con otro existente de la misma fecha.')

    def __str__(self):
        if self.cerrado:
            return f"{self.fecha:%Y-%m-%d} cerrado"
        return f"{self.fecha:%Y-%m-%d} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"
