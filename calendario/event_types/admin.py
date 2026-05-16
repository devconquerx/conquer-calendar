from django.contrib import admin
from .models import EventType, EventTypeXHost


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'host', 'duracion_minutos', 'slug_equipo', 'activo', 'fecha_actualizacion')
    list_filter = ('activo',)
    search_fields = ('nombre', 'host__username', 'host__email')
    fields = ('host', 'nombre', 'slug', 'slug_equipo', 'descripcion', 'duracion_minutos',
              'buffer_antes_minutos', 'buffer_despues_minutos', 'aviso_minimo_horas',
              'aviso_maximo_dias', 'precio', 'activo')


@admin.register(EventTypeXHost)
class EventTypeXHostAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'host', 'fecha_creacion')
    list_filter = ('event_type__activo',)
    search_fields = ('event_type__nombre', 'host__username', 'host__email')
