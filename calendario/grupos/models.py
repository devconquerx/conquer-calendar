from django.conf import settings
from django.db import models


class Grupo(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, default='')
    permite_ver_reservas_grupo = models.BooleanField(
        default=False,
        verbose_name='Pueden ver reservas del grupo',
    )
    bloquear_editar_disponibilidad = models.BooleanField(
        default=False,
        verbose_name='Bloquear edición de disponibilidad',
    )
    bloquear_editar_event_types = models.BooleanField(
        default=False,
        verbose_name='Bloquear edición de tipos de evento',
    )
    bloquear_eliminar_event_types = models.BooleanField(
        default=False,
        verbose_name='Bloquear eliminación de tipos de evento',
    )
    bloquear_crear_event_types = models.BooleanField(
        default=False,
        verbose_name='Bloquear creación de tipos de evento',
    )
    bloquear_activar_event_types = models.BooleanField(
        default=False,
        verbose_name='Bloquear activar/desactivar tipos de evento',
    )
    bloquear_cancelar_reservas = models.BooleanField(
        default=False,
        verbose_name='Bloquear cancelación de reservas propias',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'grupos'
        ordering = ['nombre']
        verbose_name = 'grupo'
        verbose_name_plural = 'grupos'

    @property
    def supervisores(self):
        from calendario.users.models import User
        return User.objects.filter(
            membresias_grupo__grupo=self,
            membresias_grupo__es_supervisor=True,
        )

    @property
    def miembros(self):
        from calendario.users.models import User
        return User.objects.filter(membresias_grupo__grupo=self)

    def __str__(self):
        return self.nombre


class GrupoXUsuario(models.Model):
    grupo = models.ForeignKey(
        Grupo, on_delete=models.CASCADE, related_name='membresias'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membresias_grupo',
    )
    es_supervisor = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'grupos_x_usuario'
        ordering = ['grupo_id', '-es_supervisor', 'id']
        verbose_name = 'miembro de grupo'
        constraints = [
            models.UniqueConstraint(fields=['grupo', 'usuario'], name='uq_grupo_x_usuario'),
        ]
        indexes = [
            models.Index(fields=['grupo', 'es_supervisor'], name='ix_gxu_grupo_supervisor'),
        ]
