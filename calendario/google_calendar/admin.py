from django.contrib import admin

from .models import GoogleCalendarEvento, GoogleCalendarSyncEstado, GoogleCalendarSyncLog


@admin.register(GoogleCalendarEvento)
class GoogleCalendarEventoAdmin(admin.ModelAdmin):
    list_display = ('host', 'google_event_id', 'inicio_utc', 'fin_utc', 'transparencia', 'estado', 'actualizado_en')
    list_filter = ('transparencia', 'estado', 'es_todo_el_dia')
    search_fields = ('host__email', 'google_event_id')
    ordering = ('host', 'inicio_utc')
    readonly_fields = ('actualizado_en',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GoogleCalendarSyncLog)
class GoogleCalendarSyncLogAdmin(admin.ModelAdmin):
    list_display = ('ejecutado_en', 'comando', 'total', 'exitosos', 'fallidos', 'hosts_fallidos')
    list_filter = ('comando',)
    ordering = ('-ejecutado_en',)
    readonly_fields = ('ejecutado_en', 'comando', 'total', 'exitosos', 'fallidos', 'hosts_fallidos')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GoogleCalendarSyncEstado)
class GoogleCalendarSyncEstadoAdmin(admin.ModelAdmin):
    list_display = ('host', 'estado', 'ultima_sync_utc', 'canal_expira_utc', 'canal_id')
    list_filter = ('estado',)
    search_fields = ('host__email', 'canal_id')
    readonly_fields = ('sync_token', 'canal_id', 'canal_resource_id', 'canal_expira_utc', 'ultima_sync_utc')

    def has_add_permission(self, request):
        return False
