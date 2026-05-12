from django.conf import settings
from django.db import models


class Permiso(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'permisos'
        ordering = ['codename']

    def __str__(self):
        return self.nombre


class Rol(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    permisos = models.ManyToManyField(Permiso, through='PermisoXRol', related_name='roles')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class RolXUsuario(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='roles_asignados'
    )
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='asignaciones')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles_x_usuario'
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'rol'], name='uq_rol_x_usuario'),
        ]


class PermisoXRol(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)
    permiso = models.ForeignKey(Permiso, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'permisos_x_roles'
        constraints = [
            models.UniqueConstraint(fields=['rol', 'permiso'], name='uq_permiso_x_rol'),
        ]
