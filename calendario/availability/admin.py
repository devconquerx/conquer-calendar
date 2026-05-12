from django.contrib import admin
from .models import BloqueHorarioSemanal


@admin.register(BloqueHorarioSemanal)
class BloqueHorarioSemanalAdmin(admin.ModelAdmin):
    list_display = ('host', 'dia_semana', 'hora_inicio', 'hora_fin')
    list_filter = ('dia_semana',)
    search_fields = ('host__username',)
