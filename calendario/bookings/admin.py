import json

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe

from .models import ConfigCorreoDefault, ConfigCorreoEvento, ConfigCorreoGrupo, LogCorreo, PlantillaCorreo, Reserva


VARIABLES_CORREO = [
    ('{{nombre_invitado}}',     'Nombre del invitado'),
    ('{{email_invitado}}',      'Email del invitado'),
    ('{{telefono_invitado}}',   'Teléfono del invitado'),
    ('{{nombre_host}}',         'Nombre del host'),
    ('{{email_host}}',          'Email del host (organizador)'),
    ('{{nombre_evento}}',       'Nombre del evento'),
    ('{{fecha_hora_invitado}}', 'Fecha y hora (TZ del invitado)'),
    ('{{fecha_hora_host}}',     'Fecha y hora (TZ del host)'),
    ('{{timezone}}',            'Zona horaria del invitado'),
    ('{{timezone_host}}',       'Zona horaria del host'),
    ('{{fecha_hora_utc}}',      'Hora en UTC'),
    ('{{duracion}}',            'Duración en minutos'),
    ('{{google_event_url}}',    'Enlace Google Calendar'),
    ('{{google_meet_url}}',     'Enlace Google Meet'),
    ('{{link_reserva}}',        'Ver reserva en la app'),
    ('{{link_cancelar}}',       'Enlace de cancelación'),
]


class PlantillaCorreoAdminForm(forms.ModelForm):
    variables = forms.MultipleChoiceField(
        choices=VARIABLES_CORREO,
        required=False,
        widget=FilteredSelectMultiple('variables en el correo', is_stacked=False),
        label='Campos visibles en el correo',
        help_text='Los campos seleccionados aparecerán en el bloque de información del correo.',
    )

    class Meta:
        model = PlantillaCorreo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['variables'].initial = self.instance.campos_visibles or []

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.campos_visibles = self.cleaned_data.get('variables', [])
        if commit:
            instance.save()
        return instance


@admin.register(PlantillaCorreo)
class PlantillaCorreoAdmin(admin.ModelAdmin):
    form = PlantillaCorreoAdminForm
    list_display = ('nombre', 'activa', 'recordatorio_1_activo', 'recordatorio_1_horas',
                    'recordatorio_2_activo', 'recordatorio_2_horas', 'fecha_creacion', 'ver_preview')
    list_filter = ('activa',)
    search_fields = ('nombre',)
    readonly_fields = ('ver_preview',)
    fieldsets = (
        ('Identidad visual', {
            'fields': ('nombre', 'logo', 'color_encabezado', 'ver_preview'),
            'description': 'Color en formato hexadecimal, ej: #111827 (negro), #1a56db (azul), #16a34a (verde).',
        }),
        ('Contenido', {
            'fields': ('texto_encabezado', 'cuerpo', 'variables', 'pie_pagina'),
        }),
        ('Recordatorios', {
            'fields': (
                ('recordatorio_1_activo', 'recordatorio_1_horas'),
                ('recordatorio_2_activo', 'recordatorio_2_horas'),
            ),
        }),
        ('Estado', {
            'fields': ('activa',),
        }),
    )

    class Media:
        pass

    @admin.display(description='Preview')
    def ver_preview(self, obj):
        return format_html(
            '<a href="/panel/correos/plantillas/{}/preview/" target="_blank"'
            ' class="button">Abrir preview en nueva pestaña</a>',
            obj.pk,
        )


class ConfigCorreoEventoInlineForm(forms.ModelForm):
    class Meta:
        model = ConfigCorreoEvento
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si es un registro nuevo (sin pk), pre-cargo con los valores del global
        if not self.instance.pk:
            from .models import ConfigCorreoDefault
            cfg = ConfigCorreoDefault.get()
            self.fields['plantilla_confirmacion_host'].initial = cfg.plantilla_confirmacion_host
            self.fields['plantilla_confirmacion_inv'].initial = cfg.plantilla_confirmacion_inv
            self.fields['plantilla_recordatorio'].initial = cfg.plantilla_recordatorio


class ConfigCorreoEventoInline(admin.StackedInline):
    model = ConfigCorreoEvento
    form = ConfigCorreoEventoInlineForm
    extra = 1
    max_num = 1
    verbose_name = 'Configuración de correos'
    verbose_name_plural = 'Configuración de correos'
    fieldsets = (
        (None, {
            'description': 'Vacío = usa la configuración global. Selecciona para sobreescribir solo este evento.',
            'fields': (
                'plantilla_confirmacion_host',
                'plantilla_confirmacion_inv',
                'plantilla_recordatorio',
            ),
        }),
    )


class ConfigCorreoGrupoInline(admin.StackedInline):
    model = ConfigCorreoGrupo
    extra = 0
    verbose_name = 'Configuración de correos del grupo'
    verbose_name_plural = 'Configuración de correos del grupo'
    fieldsets = (
        (None, {
            'description': (
                'Estas plantillas aplican a todos los miembros del grupo. '
                'Si un miembro tiene su propio tipo de evento con config de correo, esa tiene prioridad.'
            ),
            'fields': (
                'plantilla_confirmacion_host',
                'plantilla_confirmacion_inv',
                'plantilla_recordatorio',
            ),
        }),
    )


@admin.register(ConfigCorreoDefault)
class ConfigCorreoDefaultAdmin(admin.ModelAdmin):
    verbose_name = 'Configuración global de correos'
    fieldsets = (
        (None, {
            'description': (
                'Plantillas que se usan cuando un tipo de evento o grupo '
                'no tiene configuración propia. Aplica a todos los hosts.'
            ),
            'fields': (
                'plantilla_confirmacion_host',
                'plantilla_confirmacion_inv',
                'plantilla_recordatorio',
            ),
        }),
    )

    def has_add_permission(self, request):
        return not ConfigCorreoDefault.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogCorreo)
class LogCorreoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'destinatario', 'exitoso_icon', 'enviado_en', 'reserva', 'ver_contenido_link')
    list_filter = ('tipo', 'exitoso')
    search_fields = ('destinatario',)
    readonly_fields = [
        f.name for f in LogCorreo._meta.fields
        if f.name not in ('html_content', 'payload')
    ] + ['html_content_preview', 'payload_preview', 'ver_contenido_link']
    exclude = ('html_content', 'payload')
    fieldsets = (
        ('Información', {
            'fields': ('reserva', 'tipo', 'plantilla', 'destinatario', 'enviado_en'),
        }),
        ('Estado', {
            'fields': ('exitoso', 'error_detalle'),
        }),
        ('Contenido', {
            'fields': ('payload_preview', 'html_content_preview', 'ver_contenido_link'),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/content/',
                self.admin_site.admin_view(self.view_email_content),
                name='bookings_logcorreo_content',
            ),
        ]
        return custom_urls + urls

    def view_email_content(self, request, pk):
        try:
            log = LogCorreo.objects.get(pk=pk)
            return HttpResponse(log.html_content, content_type='text/html')
        except LogCorreo.DoesNotExist:
            return HttpResponse('Correo no encontrado', status=404)

    @admin.display(description='Enviado', ordering='exitoso')
    def exitoso_icon(self, obj):
        if obj.exitoso:
            return format_html('<span style="color:green;font-weight:bold;">✓</span>')
        return format_html('<span style="color:red;font-weight:bold;">✗</span>')

    @admin.display(description='Ver contenido')
    def ver_contenido_link(self, obj):
        if obj.pk and obj.html_content:
            url = reverse('admin:bookings_logcorreo_content', args=[obj.pk])
            return format_html('<a href="{}" target="_blank" class="button">Ver contenido</a>', url)
        return '-'

    @admin.display(description='Contenido HTML')
    def html_content_preview(self, obj):
        if obj.html_content:
            preview = obj.html_content[:500]
            if len(obj.html_content) > 500:
                preview += '...'
            return format_html("<pre style='max-height:200px;overflow:auto;white-space:pre-wrap;'>{}</pre>", preview)
        return '-'

    @admin.display(description='Payload')
    def payload_preview(self, obj):
        if obj.payload:
            return format_html(
                "<pre style='max-height:200px;overflow:auto;'>{}</pre>",
                json.dumps(obj.payload, indent=2, ensure_ascii=False),
            )
        return '-'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
