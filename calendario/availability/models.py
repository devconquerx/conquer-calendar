from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F


class BloqueHorarioSemanal(models.Model):

    class DiaSemana(models.IntegerChoices):
        LUNES = 0, 'Lunes'
        MARTES = 1, 'Martes'
        MIERCOLES = 2, 'Miércoles'
        JUEVES = 3, 'Jueves'
        VIERNES = 4, 'Viernes'
        SABADO = 5, 'Sábado'
        DOMINGO = 6, 'Domingo'

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bloques_disponibilidad',
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bloques_horarios_semanales'
        ordering = ['host_id', 'dia_semana', 'hora_inicio']
        verbose_name = 'bloque horario semanal'
        verbose_name_plural = 'bloques horarios semanales'
        indexes = [
            models.Index(fields=['host', 'dia_semana'], name='ix_bloque_host_dia'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'dia_semana', 'hora_inicio', 'hora_fin'],
                name='uq_bloque_horario_host_dia_rango',
            ),
            models.CheckConstraint(
                check=Q(hora_fin__gt=F('hora_inicio')),
                name='ck_bloque_hora_fin_mayor_inicio',
            ),
        ]

    def clean(self):
        if self.hora_fin and self.hora_inicio and self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la de inicio.'})
        if self.host_id is None:
            return
        qs = BloqueHorarioSemanal.objects.filter(
            host_id=self.host_id, dia_semana=self.dia_semana
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
    """

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bloques_disponibilidad_fecha',
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bloques_horarios_fecha'
        ordering = ['host_id', 'fecha', 'hora_inicio']
        verbose_name = 'bloque horario por fecha'
        verbose_name_plural = 'bloques horarios por fecha'
        indexes = [
            models.Index(fields=['host', 'fecha'], name='ix_bloque_host_fecha'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['host', 'fecha', 'hora_inicio', 'hora_fin'],
                name='uq_bloque_horario_host_fecha_rango',
            ),
            models.CheckConstraint(
                check=Q(hora_fin__gt=F('hora_inicio')),
                name='ck_bloque_fecha_hora_fin_mayor_inicio',
            ),
        ]

    def clean(self):
        if self.hora_fin and self.hora_inicio and self.hora_fin <= self.hora_inicio:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la de inicio.'})
        if self.host_id is None:
            return
        qs = BloqueHorarioFecha.objects.filter(
            host_id=self.host_id, fecha=self.fecha
        ).exclude(pk=self.pk)
        if qs.filter(hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio).exists():
            raise ValidationError('Este bloque se solapa con otro existente de la misma fecha.')

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"
