from django.contrib import admin

from .models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'host', 'nombre_invitado', 'inicio_utc', 'estado', 'fecha_creacion')
    list_filter = ('estado',)
    search_fields = ('nombre_invitado', 'email_invitado', 'host__username', 'event_type__nombre')
    readonly_fields = ('confirmacion_token', 'fecha_creacion', 'fecha_actualizacion')
