from django.contrib import admin
from .models import Grupo, GrupoXUsuario


class GrupoXUsuarioInline(admin.TabularInline):
    model = GrupoXUsuario
    extra = 1


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fecha_creacion']
    inlines = [GrupoXUsuarioInline]
