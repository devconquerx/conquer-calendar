from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.html import format_html
from django_json_widget.widgets import JSONEditorWidget

from .models import FunnelForm, FunnelScoring, Prellamada
from .views import stepform_url


class FunnelFormAdminForm(forms.ModelForm):
    class Meta:
        model = FunnelForm
        fields = '__all__'

    def clean_config(self):
        config = self.cleaned_data.get('config')
        if not isinstance(config, dict):
            raise ValidationError('La configuración debe ser un objeto JSON.')
        faltan = [k for k in ('blocks', 'q_order', 'score_ranges') if k not in config]
        if faltan:
            raise ValidationError(
                'Faltan claves mínimas en la configuración: ' + ', '.join(faltan) + '.'
            )
        return config


@admin.register(FunnelForm)
class FunnelFormAdmin(admin.ModelAdmin):
    form = FunnelFormAdminForm
    list_display = ('escuela', 'region', 'key', 'nombre', 'activo')
    list_filter = ('escuela', 'region', 'activo')
    search_fields = ('key', 'slug', 'nombre')
    prepopulated_fields = {'slug': ('key',)}
    readonly_fields = ('creado_en', 'actualizado_en', 'funnel_url_botones')
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }
    fieldsets = (
        ('Identidad', {
            'fields': ('key', 'slug', 'escuela', 'region', 'nombre', 'funnel_url_botones', 'activo'),
        }),
        ('Configuración del formulario', {
            'description': (
                'JSON con blocks, q_order, validate, neverCancel, score_ranges, '
                'cancel_screen, settings, theme, messages. El scoring se calcula '
                'siempre en el backend a partir de esta configuración.'
            ),
            'fields': ('config',),
        }),
        ('Metadatos', {
            'fields': ('creado_en', 'actualizado_en'),
        }),
    )

    def funnel_url_botones(self, obj):
        if not obj or not obj.pk:
            return '—'
        path = stepform_url(obj.escuela, obj.region)
        if not path:
            return '—'
        btn_style = (
            'display:inline-block;padding:7px 16px;border-radius:4px;font-size:13px;'
            'font-weight:600;cursor:pointer;border:none;'
        )
        return format_html(
            '<a href="{path}" target="_blank" rel="noopener noreferrer" '
            '   style="{btn}background:#417690;color:#fff;text-decoration:none;margin-right:10px">'
            '   Ir al funnel ↗'
            '</a>'
            '<button type="button" data-funnel-path="{path}" '
            '   onclick="'
            '     var u=window.location.origin+this.dataset.funnelPath;'
            '     navigator.clipboard.writeText(u).then(function(){{this.textContent=\'✓ Copiado\';'
            '       setTimeout(function(){{this.textContent=\'Copiar dirección\'}}.bind(this),2000)'
            '     }}.bind(this));'
            '   " '
            '   style="{btn}background:#79aec8;color:#fff">'
            'Copiar dirección'
            '</button>',
            path=path,
            btn=btn_style,
        )
    funnel_url_botones.short_description = 'URL del funnel'


@admin.register(FunnelScoring)
class FunnelScoringAdmin(admin.ModelAdmin):
    readonly_fields = ('actualizado_en',)
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }
    fieldsets = (
        (None, {
            'description': (
                'Tabla global de puntuaciones compartida por todos los funnels '
                '(réplica de scores.jsx). Singleton — solo existe un registro.'
            ),
            'fields': ('config', 'actualizado_en'),
        }),
    )

    def has_add_permission(self, request):
        return not FunnelScoring.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


def _tag_col(done_tag, failed_tag, short_description, gated_setting=None):
    """Columna tri-estado por tags: ✅ done, ⚠️ failed, ⏳ pendiente, — si el
    destino está deshabilitado por setting."""
    def column(self, obj):
        if gated_setting and not getattr(settings, gated_setting, False):
            return format_html('<span title="deshabilitado" style="opacity:.4">—</span>')
        names = {t.name for t in obj.tags.all()}  # usa el prefetch del queryset
        if done_tag in names:
            return format_html('✅')
        if failed_tag in names:
            return format_html('⚠️')
        return format_html('⏳')
    column.short_description = short_description
    return column


@admin.register(Prellamada)
class PrellamadaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'email', 'resultado', 'score', 'event_type', 'reserva',
        'col_supabase', 'col_crm', 'creado_en',
    )
    list_filter = ('resultado', 'funnel', 'creado_en', 'tags')
    search_fields = ('nombre', 'email', 'telefono', 'token', 'journey_id', 'event_id')
    date_hierarchy = 'creado_en'
    ordering = ('-id',)
    exclude = ('tags',)
    readonly_fields = (
        'funnel', 'token', 'nombre', 'email', 'telefono', 'respuestas',
        'score', 'resultado', 'event_type', 'reserva',
        'journey_id', 'event_id', 'utm_source', 'utm_campaign', 'utm_medium',
        'utm_term', 'utm_content', 'utm_idcampaign', 'utm_adsetid', 'utm_adid',
        'utm_form_variant', 'tracking', 'creado_en',
    )

    col_supabase = _tag_col('supabase_done', 'supabase_failed', 'Supabase')
    col_crm = _tag_col('crm_done', 'crm_failed', 'CRM', gated_setting='CRM_INGEST_ENABLED')
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
