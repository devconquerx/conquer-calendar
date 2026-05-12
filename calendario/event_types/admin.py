from django.contrib import admin
from .models import EventType, EventTypeXHost


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'host', 'duracion_minutos', 'activo', 'fecha_actualizacion')
    list_filter = ('activo',)
    search_fields = ('nombre', 'host__username', 'host__email')


@admin.register(EventTypeXHost)
class EventTypeXHostAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'host', 'fecha_creacion')
    list_filter = ('event_type__activo',)
    search_fields = ('event_type__nombre', 'host__username', 'host__email')
