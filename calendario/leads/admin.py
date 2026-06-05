from django.contrib import admin

from .models import Lead, ConversionLog


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'full_name', 'school', 'utm_source', 'journey_id', 'created')
    list_filter = ('school', 'utm_source', 'is_form_vsl_processed')
    search_fields = ('email', 'full_name', 'journey_id', 'event_id', 'lead_phone')
    date_hierarchy = 'created'
    readonly_fields = ('created', 'modified')


@admin.register(ConversionLog)
class ConversionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'platform', 'event_name', 'school', 'success', 'status_code', 'created_at')
    list_filter = ('platform', 'success', 'school')
    search_fields = ('event_id', 'event_name', 'error_message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
