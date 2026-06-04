from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
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
    list_display = ('tipo', 'destinatario', 'exitoso', 'enviado_en', 'reserva')
    list_filter = ('tipo', 'exitoso')
    search_fields = ('destinatario',)
    readonly_fields = [f.name for f in LogCorreo._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
