from django.contrib import admin
from django.utils.html import format_html
from .models import Lead, ConversionLog
from .services.utils import is_from_meta, is_from_tiktok, is_from_google
from calendario.monitoring.models import TaskFailureLog, AlertLog


class TaskFailureInline(admin.TabularInline):
    model = TaskFailureLog
    fk_name = 'lead'
    extra = 0
    fields = ('created', 'task_name', 'exception_type', 'exception_message', 'sentry_link')
    readonly_fields = ('created', 'task_name', 'exception_type', 'exception_message', 'sentry_link')
    ordering = ('-created',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def sentry_link(self, obj):
        if obj.sentry_url:
            return format_html('<a href="{}" target="_blank">Ver en Sentry</a>', obj.sentry_url)
        return '—'
    sentry_link.short_description = 'Sentry'


class AlertLogInline(admin.TabularInline):
    model = AlertLog
    fk_name = 'lead'
    extra = 0
    fields = ('created', 'metric', 'message')
    readonly_fields = ('created', 'metric', 'message')
    ordering = ('-created',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


def _tag_check(done_tag, failed_tag, task_name_fragment, short_description, applies=None):
    """Factory de columnas de estado: ✅ done, ⚠️ failed (link a Sentry),
    ⏳ pendiente, — no aplica.

    `applies(lead) -> bool` decide si la tarea le corresponde al lead (p.ej. solo
    los de Meta se envían a Meta CAPI). Si no aplica y no hay tag done/failed,
    se muestra "—" en vez del reloj de arena (que es solo para lo pendiente)."""
    def column(self, obj):
        names = getattr(obj, '_prefetched_tag_names', set())
        if done_tag in names:
            return format_html('✅')
        if failed_tag in names:
            failure = getattr(obj, '_prefetched_failures', {}).get(task_name_fragment)
            if failure and failure.sentry_url:
                return format_html('<a href="{}" target="_blank" title="{}">⚠️</a>', failure.sentry_url, failure.exception_message)
            return format_html('⚠️')
        if applies is not None and not applies(obj):
            return format_html('<span style="color:#ccc">—</span>')
        return format_html('⏳')
    column.short_description = short_description
    column.admin_order_field = None
    return column


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'full_name', 'school', 'utm_source',
        'col_meta', 'col_tiktok', 'col_google', 'col_respondio',
        'col_ac', 'col_nb', 'col_crm', 'col_supabase',
        'created',
    )
    list_filter = ('school', 'utm_source', 'is_form_vsl_processed', 'setter_conversation_status', 'tags')
    search_fields = ('email', 'full_name', 'journey_id')
    readonly_fields = ('created', 'modified', 'tag_chips_detail')
    ordering = ('-created',)
    exclude = ('tags',)
    inlines = [TaskFailureInline, AlertLogInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')

    col_meta = _tag_check('meta_capi_done', 'meta_capi_failed', 'process_meta_capi', 'Meta', applies=is_from_meta)
    col_tiktok = _tag_check('tiktok_events_done', 'tiktok_events_failed', 'process_tiktok_events', 'TikTok', applies=is_from_tiktok)
    col_google = _tag_check('google_ads_done', 'google_ads_failed', 'process_google_ads', 'Google', applies=is_from_google)
    col_respondio = _tag_check('respondio_done', 'respondio_failed', 'process_respondio', 'Respondio', applies=lambda l: bool(l.lead_phone))
    col_ac = _tag_check('activecampaign_done', 'activecampaign_failed', 'process_activecampaign', 'AC', applies=lambda l: bool(l.email))
    col_nb = _tag_check('neverbounce_done', 'neverbounce_failed', 'process_neverbounce', 'NB', applies=lambda l: bool(l.email))
    col_crm = _tag_check('crm_done', 'crm_failed', 'process_crm_send', 'CRM', applies=lambda l: bool(l.email))
    col_supabase = _tag_check('supabase_done', 'supabase_failed', 'process_supabase', 'SP')

    def _render_chips(self, obj):
        colors = {
            'meta_capi_done': '#1877F2',
            'tiktok_events_done': '#000000',
            'google_ads_done': '#4285F4',
            'respondio_done': '#00C853',
            'activecampaign_done': '#356AE6',
            'neverbounce_done': '#7B1FA2',
            'crm_done': '#FF6F00',
        }
        chips = []
        for tag in obj.tags.all():
            color = colors.get(tag.name, '#666')
            chips.append(
                f'<span style="display:inline-block;padding:3px 10px;margin:2px;'
                f'border-radius:12px;font-size:11px;font-weight:600;'
                f'color:#fff;background:{color}">{tag.name}</span>'
            )
        return format_html(''.join(chips)) if chips else format_html('<span style="color:#999">—</span>')

    def tag_chips_detail(self, obj):
        return self._render_chips(obj)
    tag_chips_detail.short_description = 'Processing Tags'

    def changelist_view(self, request, extra_context=None):
        """Inyecta tags y fallos prefetcheados en cada objeto para las columnas tri-estado."""
        response = super().changelist_view(request, extra_context)
        if hasattr(response, 'context_data') and 'cl' in response.context_data:
            lead_ids = [obj.pk for obj in response.context_data['cl'].result_list]
            failures_by_lead = {}
            if lead_ids:
                failures = TaskFailureLog.objects.filter(lead_id__in=lead_ids).order_by('-created')
                for f in failures:
                    key = (f.lead_id, f.task_name)
                    if key not in failures_by_lead:
                        failures_by_lead[key] = f

            for obj in response.context_data['cl'].result_list:
                obj._prefetched_tag_names = set(t.name for t in obj.tags.all())
                obj._prefetched_failures = {}
                for (lead_id, task_name), failure in failures_by_lead.items():
                    if lead_id == obj.pk:
                        short_name = task_name.rsplit('.', 1)[-1] if '.' in task_name else task_name
                        obj._prefetched_failures[short_name] = failure
        return response


@admin.register(ConversionLog)
class ConversionLogAdmin(admin.ModelAdmin):
    list_display = ('platform', 'event_name', 'school', 'success', 'status_code', 'execution_time_ms', 'created_at')
    list_filter = ('platform', 'success', 'school')
    search_fields = ('event_id', 'pixel_id')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
