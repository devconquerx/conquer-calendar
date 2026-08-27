from django.contrib import admin
from .models import BloqueHorarioFecha, BloqueHorarioSemanal, Horario


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'host', 'es_default')
    list_filter = ('es_default',)
    search_fields = ('nombre', 'host__username', 'host__email')
    autocomplete_fields = ('host',)


@admin.register(BloqueHorarioSemanal)
class BloqueHorarioSemanalAdmin(admin.ModelAdmin):
    list_display = ('horario', 'dia_semana', 'hora_inicio', 'hora_fin')
    list_filter = ('dia_semana',)
    search_fields = ('horario__nombre', 'horario__host__username')


@admin.register(BloqueHorarioFecha)
class BloqueHorarioFechaAdmin(admin.ModelAdmin):
    list_display = ('horario', 'fecha', 'hora_inicio', 'hora_fin')
    list_filter = ('fecha',)
    search_fields = ('horario__nombre', 'horario__host__username')
