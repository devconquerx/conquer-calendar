from django.contrib import admin
from django.utils.safestring import mark_safe

from calendario.bookings.admin import ConfigCorreoEventoInline

from .models import EventType, EventTypeXHost


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'host', 'duracion_minutos', 'slug_equipo', 'activo', 'crm_destino', 'registrar_en_academia', 'fecha_actualizacion')
    list_filter = ('activo', 'crm_destino', 'registrar_en_academia')
    search_fields = ('nombre', 'host__username', 'host__email')
    readonly_fields = ('id',)
    fields = ('id', 'host', 'nombre', 'slug', 'slug_equipo', 'descripcion', 'duracion_minutos',
              'buffer_antes_minutos', 'buffer_despues_minutos', 'aviso_minimo_minutos',
              'aviso_maximo_dias', 'precio', 'activo', 'crm_destino',
              'registrar_en_academia', 'academia_lms_id',
              'confirmacion_tipo', 'confirmacion_url')
    inlines = [ConfigCorreoEventoInline]
    actions = ('activar_registro_academia', 'desactivar_registro_academia')

    # Qué se registra en la academia se decide tipo de evento a tipo de evento, y
    # van a ser muchos: marcarlos de uno en uno desde el formulario es la clase de
    # tarea que acaba resolviéndose con un script suelto que nadie vuelve a ver.
    # Con el filtro «registrar_en_academia» de la derecha y estas dos acciones se
    # hace desde el admin, en lote, sin tocar la base a mano.
    @admin.action(description='Registrar las sesiones en la academia')
    def activar_registro_academia(self, request, queryset):
        n = queryset.update(registrar_en_academia=True)
        self.message_user(request, f'{n} tipo(s) de evento pasan a registrarse en la academia.')

    @admin.action(description='Dejar de registrar las sesiones en la academia')
    def desactivar_registro_academia(self, request, queryset):
        n = queryset.update(registrar_en_academia=False)
        self.message_user(request, f'{n} tipo(s) de evento dejan de registrarse en la academia.')

    class Media:
        js = ('admin/js/confirmacion_toggle.js',)


@admin.register(EventTypeXHost)
class EventTypeXHostAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'host', 'fecha_creacion')
    list_filter = ('event_type__activo',)
    search_fields = ('event_type__nombre', 'host__username', 'host__email')
