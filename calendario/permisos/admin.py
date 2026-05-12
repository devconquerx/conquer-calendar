from django.contrib import admin
from .models import Permiso, Rol, RolXUsuario, PermisoXRol


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ('codename', 'nombre', 'fecha_creacion')
    search_fields = ('codename', 'nombre')


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(RolXUsuario)
class RolXUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'fecha_creacion')


@admin.register(PermisoXRol)
class PermisoXRolAdmin(admin.ModelAdmin):
    list_display = ('rol', 'permiso', 'fecha_creacion')
