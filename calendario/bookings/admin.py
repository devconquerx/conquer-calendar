import json

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Q
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe

from .models import (ConfigCorreoDefault, ConfigCorreoEvento, ConfigCorreoGrupo, DominioRemitente,
                     LogCorreo, PlantillaCorreo, Reserva)
from calendario.event_types.models import EventType
from calendario.leads.admin import _tag_check
from calendario.monitoring.models import TaskFailureLog, AlertLog


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
    ('{{link_cancelar}}',       'Botón: cancelar reserva'),
    ('{{link_reagendar}}',      'Botón: reagendar (vuelve a la página del evento)'),
    ('{{link_confirmar}}',      'Botón: confirmar asistencia'),
]


@admin.register(DominioRemitente)
class DominioRemitenteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dominio', 'region', 'from_email', 'reply_to', 'activo', 'plantillas_que_lo_usan')
    list_filter = ('region', 'activo')
    search_fields = ('nombre', 'dominio', 'from_email', 'reply_to')
    fieldsets = (
        (None, {
            'fields': ('nombre', 'dominio', 'activo'),
        }),
        ('Mailgun', {
            'fields': ('region',),
            'description': (
                'La región tiene que ser la misma en la que está dado de alta el dominio en Mailgun. '
                'Si no coincide, el envío falla con «Unknown sender domain» aunque el dominio esté verificado.'
            ),
        }),
        ('Direcciones', {
            'fields': ('from_email', 'reply_to'),
            'description': (
                'El «From» es desde donde sale el correo; el «Reply-To» es a dónde llegan las respuestas '
                'cuando el destinatario le da a Responder. Pueden ser distintos: lo normal es enviar desde '
                'noreply@ y recibir las respuestas en un buzón que alguien atienda.'
            ),
        }),
    )

    @admin.display(description='Plantillas')
    def plantillas_que_lo_usan(self, obj):
        return obj.plantillas.count()


# Los tres huecos de ConfigCorreoEvento, para poder asignar la plantilla a varios
# tipos de evento de una vez desde la propia plantilla en vez de ir uno por uno.
# (campo del modelo ConfigCorreoEvento, campo del formulario, etiqueta)
ROLES_PLANTILLA = (
    ('plantilla_confirmacion_host', 'tipos_correo_host', 'Correo al host'),
    ('plantilla_confirmacion_inv', 'tipos_correo_invitado', 'Correo al invitado'),
    ('plantilla_recordatorio', 'tipos_recordatorio', 'Correo de recordatorio'),
)


class TiposEventoField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        etiqueta = f'{obj.nombre} — {obj.host}'
        return etiqueta if obj.activo else f'{etiqueta} (inactivo)'


def _campo_tipos_evento(etiqueta):
    return TiposEventoField(
        queryset=EventType.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('tipos de evento', is_stacked=False),
        label=etiqueta,
    )


class PlantillaCorreoAdminForm(forms.ModelForm):
    variables = forms.MultipleChoiceField(
        choices=VARIABLES_CORREO,
        required=False,
        widget=FilteredSelectMultiple('variables en el correo', is_stacked=False),
        label='Campos visibles en el correo',
        help_text='Los campos seleccionados aparecerán en el bloque de información del correo.',
    )
    tipos_correo_host = _campo_tipos_evento('Correo al host')
    tipos_correo_invitado = _campo_tipos_evento('Correo al invitado')
    tipos_recordatorio = _campo_tipos_evento('Correo de recordatorio')

    class Meta:
        model = PlantillaCorreo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['variables'].initial = self.instance.campos_visibles or []

        for campo_config, campo_form, _etiqueta in ROLES_PLANTILLA:
            ya_asignados = self._tipos_asignados(campo_config)
            # Los inactivos no se ofrecen, pero si alguno ya usa la plantilla tiene
            # que seguir en la lista: si no, al guardar se quedaría fuera de la
            # selección y lo desasignaríamos sin que nadie lo haya pedido.
            self.fields[campo_form].queryset = (
                EventType.objects
                .filter(Q(activo=True) | Q(pk__in=ya_asignados))
                .select_related('host')
            )
            self.fields[campo_form].initial = list(ya_asignados)

    def _tipos_asignados(self, campo_config):
        """IDs de los tipos de evento que ya usan esta plantilla en ese hueco."""
        if not self.instance.pk:
            return []
        return list(
            ConfigCorreoEvento.objects
            .filter(**{campo_config: self.instance})
            .values_list('event_type_id', flat=True)
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.campos_visibles = self.cleaned_data.get('variables', [])
        if commit:
            instance.save()
            self.save_m2m()
            self._sincronizar_tipos_evento(instance)
        else:
            # El admin guarda con commit=False y llama a save_m2m() después, cuando
            # la plantilla ya tiene pk: es el momento de tocar las configs.
            guardar_m2m = self.save_m2m

            def _save_m2m():
                guardar_m2m()
                self._sincronizar_tipos_evento(instance)

            self.save_m2m = _save_m2m
        return instance

    def _sincronizar_tipos_evento(self, plantilla):
        tocados = set()

        for campo_config, campo_form, _etiqueta in ROLES_PLANTILLA:
            elegidos = self.cleaned_data.get(campo_form)
            if elegidos is None:
                continue
            ids = {tipo.pk for tipo in elegidos}

            # Quitar de la caja = ese hueco vuelve a vacío, o sea a la config
            # global (o la del grupo). No se borra la plantilla, solo el vínculo.
            sobran = ConfigCorreoEvento.objects.filter(
                **{campo_config: plantilla}
            ).exclude(event_type_id__in=ids)
            tocados.update(sobran.values_list('event_type_id', flat=True))
            sobran.update(**{campo_config: None})

            for tipo_id in ids:
                config, _creada = ConfigCorreoEvento.objects.get_or_create(event_type_id=tipo_id)
                if getattr(config, f'{campo_config}_id') != plantilla.pk:
                    setattr(config, campo_config, plantilla)
                    config.save(update_fields=[campo_config])
                tocados.add(tipo_id)

        # Una config con los tres huecos vacíos no aporta nada y además hace que el
        # inline del tipo de evento deje de precargar los valores globales.
        if tocados:
            ConfigCorreoEvento.objects.filter(
                event_type_id__in=tocados,
                plantilla_confirmacion_host__isnull=True,
                plantilla_confirmacion_inv__isnull=True,
                plantilla_recordatorio__isnull=True,
            ).delete()


@admin.register(PlantillaCorreo)
class PlantillaCorreoAdmin(admin.ModelAdmin):
    form = PlantillaCorreoAdminForm
    list_display = ('nombre', 'dominio', 'formato', 'activa', 'tipos_que_la_usan',
                    'recordatorio_1_activo', 'recordatorio_1_horas',
                    'recordatorio_2_activo', 'recordatorio_2_horas', 'fecha_creacion', 'ver_preview')
    list_filter = ('activa', 'formato', 'dominio')
    search_fields = ('nombre',)
    readonly_fields = ('ver_preview',)
    fieldsets = (
        ('Envío', {
            'fields': ('dominio', 'formato'),
            'description': (
                'Desde qué dominio sale este correo y en qué formato. Si dejas el dominio vacío se usa '
                'el remitente por defecto de la app. En texto plano se ignoran el logo y los colores.'
            ),
        }),
        ('Identidad visual', {
            'fields': ('nombre', 'logo', 'color_encabezado', 'ver_preview'),
            'description': 'Color en formato hexadecimal, ej: #111827 (negro), #1a56db (azul), #16a34a (verde). Solo aplica en formato HTML.',
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
        ('Aplicar esta plantilla a tipos de evento', {
            'fields': ('tipos_correo_host', 'tipos_correo_invitado', 'tipos_recordatorio'),
            'description': (
                'Asigna esta plantilla a varios tipos de evento de una vez, sin entrar en cada uno. '
                'A la derecha están los que ya la usan en ese correo. '
                'Quitar uno de la derecha no borra nada: ese tipo de evento vuelve a la configuración '
                'global (o a la de su grupo) para ese correo. '
                'Solo se listan los tipos de evento activos.'
            ),
        }),
    )

    class Media:
        pass

    @admin.display(description='Tipos de evento')
    def tipos_que_la_usan(self, obj):
        partes = []
        for etiqueta, related in (('host', 'configs_confirmacion_host'),
                                  ('invitado', 'configs_confirmacion_inv'),
                                  ('recordatorio', 'configs_recordatorio_evento')):
            total = getattr(obj, related).count()
            if total:
                partes.append(f'{etiqueta}: {total}')
        return ' · '.join(partes) or '—'

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


class ReservaTaskFailureInline(admin.TabularInline):
    model = TaskFailureLog
    fk_name = 'reserva'
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


class ReservaAlertLogInline(admin.TabularInline):
    model = AlertLog
    fk_name = 'reserva'
    extra = 0
    fields = ('created', 'metric', 'message')
    readonly_fields = ('created', 'metric', 'message')
    ordering = ('-created',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


def _sch_source(obj):
    """utm_source normalizado de la reserva, para decidir qué columnas de ads aplican."""
    return (obj.utm_source or '').lower()


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_invitado', 'email_invitado', 'event_type', 'host',
        'inicio_utc', 'estado', 'asistencia_confirmada', 'google_sync_estado',
        'col_meta', 'col_tiktok', 'col_google', 'col_ac',
        'col_respondio', 'col_crm', 'col_onboarding', 'col_supabase',
        'fecha_creacion',
    )
    list_filter = ('estado', 'asistencia_confirmada', 'google_sync_estado', 'event_type', 'host', 'fecha_creacion', 'tags')
    search_fields = (
        'nombre_invitado', 'email_invitado', 'telefono_invitado',
        'google_event_id', 'confirmacion_token', 'journey_id', 'event_id',
    )
    date_hierarchy = 'fecha_creacion'
    ordering = ('-fecha_creacion',)
    raw_id_fields = ('event_type', 'host')
    list_select_related = ('event_type', 'host')
    inlines = [ReservaTaskFailureInline, ReservaAlertLogInline]
    readonly_fields = (
        'confirmacion_token', 'google_event_id', 'google_event_link',
        'google_meet_url', 'fecha_creacion', 'fecha_actualizacion',
        'tag_chips_detail', 'asistencia_confirmada_en',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event_type', 'host').prefetch_related('tags')

    # Columnas tri-estado de ejecución de las tareas de conversión del schedule.
    # Mismo factory que LeadAdmin: ✅ done / ⚠️ failed (link Sentry) / ⏳ pendiente / — no aplica.
    # Meta/TikTok/Google aplican según utm_source; AC con email; Respondio con teléfono;
    # CRM solo si el event_type tiene marcado "Notificar al CRM" (si no, queda en —).
    col_meta = _tag_check('sch_meta_capi_done', 'sch_meta_capi_failed', 'process_schedule_meta_capi', 'Meta', applies=lambda r: _sch_source(r) == 'metaads')
    col_tiktok = _tag_check('sch_tiktok_events_done', 'sch_tiktok_events_failed', 'process_schedule_tiktok_events', 'TikTok', applies=lambda r: 'tiktok' in _sch_source(r))
    col_google = _tag_check('sch_google_ads_done', 'sch_google_ads_failed', 'process_schedule_google_ads', 'Google', applies=lambda r: _sch_source(r) == 'googleads')
    col_ac = _tag_check('sch_activecampaign_done', 'sch_activecampaign_failed', 'process_schedule_activecampaign', 'AC', applies=lambda r: bool(r.email_invitado))
    col_respondio = _tag_check('sch_respondio_done', 'sch_respondio_failed', 'process_schedule_respondio', 'Respondio', applies=lambda r: bool(r.telefono_invitado))
    # CRM: el destino depende de event_type.crm_destino. Cada columna aplica solo a su destino.
    col_crm = _tag_check('sch_crm_done', 'sch_crm_failed', 'process_schedule_crm', 'CRM·Sched', applies=lambda r: bool(r.event_type and r.event_type.crm_destino == 'schedule'))
    col_onboarding = _tag_check('sch_onboarding_done', 'sch_onboarding_failed', 'process_onboarding_session', 'CRM·ONB', applies=lambda r: bool(r.event_type and r.event_type.crm_destino == 'onboarding'))
    col_supabase = _tag_check('sch_supabase_done', 'sch_supabase_failed', 'process_schedule_supabase', 'SP')

    def _render_chips(self, obj):
        colors = {
            'sch_meta_capi_done': '#1877F2',
            'sch_tiktok_events_done': '#000000',
            'sch_google_ads_done': '#4285F4',
            'sch_respondio_done': '#00C853',
            'sch_activecampaign_done': '#356AE6',
            'sch_crm_done': '#FF6F00',
            'sch_onboarding_done': '#FF6F00',
            'sch_supabase_done': '#3ECF8E',
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
        """Inyecta tags y fallos prefetcheados en cada reserva para las columnas tri-estado."""
        response = super().changelist_view(request, extra_context)
        if hasattr(response, 'context_data') and 'cl' in response.context_data:
            reserva_ids = [obj.pk for obj in response.context_data['cl'].result_list]
            failures_by_reserva = {}
            if reserva_ids:
                failures = TaskFailureLog.objects.filter(reserva_id__in=reserva_ids).order_by('-created')
                for f in failures:
                    key = (f.reserva_id, f.task_name)
                    if key not in failures_by_reserva:
                        failures_by_reserva[key] = f

            for obj in response.context_data['cl'].result_list:
                obj._prefetched_tag_names = set(t.name for t in obj.tags.all())
                obj._prefetched_failures = {}
                for (reserva_id, task_name), failure in failures_by_reserva.items():
                    if reserva_id == obj.pk:
                        short_name = task_name.rsplit('.', 1)[-1] if '.' in task_name else task_name
                        obj._prefetched_failures[short_name] = failure
        return response
    fieldsets = (
        ('Invitado', {
            'fields': ('nombre_invitado', 'email_invitado', 'telefono_invitado',
                       'timezone_invitado', 'notas'),
        }),
        ('Evento', {
            'fields': ('event_type', 'host', 'inicio_utc', 'fin_utc', 'estado'),
        }),
        ('Google Calendar', {
            'fields': ('google_sync_estado', 'google_event_id', 'google_event_link',
                       'google_meet_url'),
        }),
        ('Recordatorios', {
            'fields': ('recordatorio_1_enviado', 'recordatorio_2_enviado'),
        }),
        ('Tracking', {
            'fields': (
                'journey_id', 'event_id', 'utm_source', 'utm_campaign', 'utm_medium',
                'utm_term', 'utm_content', 'utm_idcampaign', 'utm_adsetid', 'utm_adid',
                'utm_form_variant', 'url',
            ),
        }),
        ('Metadatos', {
            'fields': ('confirmacion_token', 'tag_chips_detail', 'tags', 'fecha_creacion', 'fecha_actualizacion'),
        }),
    )

    @admin.display(description='Evento en Google Calendar')
    def google_event_link(self, obj):
        url = obj.google_event_url
        if url:
            return format_html('<a href="{}" target="_blank">Abrir en Google Calendar</a>', url)
        return '-'
