from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_json_widget.widgets import JSONEditorWidget

from . import contenido
from .models import ContenidoDeEvento, FunnelForm, FunnelScoring, Prellamada
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
        'col_supabase', 'col_crm', 'col_respondio', 'creado_en',
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
    col_respondio = _tag_col('respondio_done', 'respondio_failed', 'Respondio')
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



# ─── Textos de las páginas de evento ─────────────────────────────────────────
# La pantalla buena para escribir la copia es la del panel
# (/panel/contenido/), con editor de HTML y vista previa. Esto de aquí se
# mantiene como puerta de atrás para quien ya vive en el admin: edita y publica
# de una vez, sin pasar por el borrador.

class ContenidoDeEventoForm(forms.ModelForm):
    """Formulario dinámico: un campo por texto declarado en el esquema."""

    class Meta:
        model = ContenidoDeEvento
        # `textos` no se edita a mano: lo componen los campos de abajo.
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clave = self.instance.clave
        self.campos_esquema = contenido.campos_de(clave)
        # Se parte de lo que se ve hoy en la página: publicado, o el texto del
        # código donde no haya nada publicado.
        escritos = contenido.a_formulario(clave, contenido.valores_de(clave))
        for campo in self.campos_esquema:
            if campo.tipo == contenido.GRUPO:
                for i in range(campo.filas):
                    for sub in campo.subcampos:
                        nombre = contenido.nombre_campo(campo, i, sub)
                        etiqueta = f'{campo.etiqueta.rstrip("s")} {i + 1} · {sub.etiqueta}'
                        self.fields[nombre] = self._campo(sub, escritos.get(nombre, ''), etiqueta)
            else:
                nombre = contenido.nombre_campo(campo)
                self.fields[nombre] = self._campo(campo, escritos.get(nombre, ''))

    def _campo(self, campo, valor, etiqueta=None):
        """Un campo del formulario a partir de su declaración en el esquema."""
        comun = {
            'label': etiqueta or campo.etiqueta,
            'help_text': campo.ayuda,
            'required': False,
            'initial': valor,
        }
        if campo.tipo == contenido.LISTA:
            filas = max(3, valor.count('\n') + 1)
            return forms.CharField(widget=forms.Textarea(attrs={'rows': filas, 'cols': 100}), **comun)
        if campo.tipo == contenido.HTML:
            return forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'cols': 100}), **comun)
        return forms.CharField(widget=forms.TextInput(attrs={'size': 100}), **comun)

    def clean(self):
        datos = super().clean()
        for nombre in contenido.errores_de_html(self.instance.clave, datos):
            self.add_error(nombre, mark_safe(contenido.ERROR_HTML))
        return datos

    def save(self, commit=True):
        """Publica directamente: en el admin no hay borrador."""
        self.instance.textos = contenido.desde_formulario(self.instance.clave, self.cleaned_data)
        self.instance.borrador = {}
        self.instance.publicado_en = timezone.now()
        return super().save(commit=commit)


@admin.register(ContenidoDeEvento)
class ContenidoDeEventoAdmin(admin.ModelAdmin):
    form = ContenidoDeEventoForm
    list_display = ('col_pagina', 'col_escuela', 'col_tipo', 'col_editado', 'col_borrador',
                    'publicado_en')
    readonly_fields = ('col_enlaces',)
    actions = ('restaurar_textos_originales',)

    def get_form(self, request, obj=None, change=False, **kwargs):
        """Los campos del formulario no son columnas del modelo.

        Los construye `ContenidoDeEventoForm` a partir del esquema, así que no
        se le pasa la lista de `fieldsets`: Django la validaría contra el modelo
        y no encontraría ninguno.
        """
        kwargs['fields'] = None
        return super().get_form(request, obj, change=change, **kwargs)

    def get_queryset(self, request):
        """Las filas salen en el orden de la tabla de /funnels/, no alfabético."""
        orden = models.Case(
            *[models.When(clave=clave, then=i) for i, clave in enumerate(contenido.PAGINAS)],
            default=len(contenido.PAGINAS),
            output_field=models.IntegerField(),
        )
        return super().get_queryset(request).annotate(_orden=orden).order_by('_orden')

    # Las filas las crea la migración, una por página con plantilla: ni se
    # añaden ni se borran desde aquí.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fieldsets(self, request, obj=None):
        """Un bloque por sección de la página, en el orden en que se leen."""
        campos_pagina = contenido.campos_de(obj.clave if obj else '')
        secciones = []
        for campo in campos_pagina:
            if campo.seccion not in secciones:
                secciones.append(campo.seccion)
        bloques = [(None, {
            'description': (
                'Los textos de esta página. Se admite HTML de maquetado '
                '(&lt;strong&gt;, &lt;em&gt;, &lt;u&gt;, &lt;br&gt;, enlaces): lo que envuelvas '
                'en &lt;strong&gt;…&lt;/strong&gt; se pinta con el color de resalte de la '
                'página. Una caja vacía no borra nada: ese texto vuelve a ser el original, así '
                'que vaciarla es la forma de deshacer un cambio. '
                'Guardar aquí PUBLICA el cambio; para escribir con vista previa antes de '
                'publicar, usa la pantalla del panel.'
            ),
            'fields': ('col_enlaces',),
        })]
        for seccion in secciones:
            campos = []
            for campo in campos_pagina:
                if campo.seccion != seccion:
                    continue
                if campo.tipo == contenido.GRUPO:
                    campos += [contenido.nombre_campo(campo, i, sub)
                               for i in range(campo.filas) for sub in campo.subcampos]
                else:
                    campos.append(contenido.nombre_campo(campo))
            bloques.append((seccion, {'fields': tuple(campos)}))
        return bloques

    @admin.display(description='Página')
    def col_pagina(self, obj):
        return obj.pagina.nombre if obj.pagina else obj.clave

    @admin.display(description='Escuela')
    def col_escuela(self, obj):
        return obj.pagina.escuela if obj.pagina else '—'

    @admin.display(description='Tipo')
    def col_tipo(self, obj):
        return dict(lanzamiento='Lanzamiento', gracias='Gracias',
                    campana='Campaña').get(obj.pagina.tipo if obj.pagina else '', '—')

    @admin.display(description='¿Editada?', boolean=True)
    def col_editado(self, obj):
        return bool(obj.textos)

    @admin.display(description='Borrador sin publicar', boolean=True)
    def col_borrador(self, obj):
        return obj.hay_cambios_sin_publicar

    @admin.display(description='Ver la página')
    def col_enlaces(self, obj):
        pagina = obj.pagina if obj else None
        if not pagina or not pagina.vista_previa:
            return '—'
        estilo = ('display:inline-block;padding:7px 16px;border-radius:4px;font-size:13px;'
                  'font-weight:600;background:#417690;color:#fff;text-decoration:none;'
                  'margin-right:10px')
        enlaces = [format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer" style="{}">Ver la página ↗</a>',
            pagina.url_publica(), estilo)]
        if pagina.tiene_v2:
            enlaces.append(format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer" style="{}">Ver la versión 2 ↗</a>',
                pagina.url_publica(v2=True), estilo))
        enlaces.append(format_html(
            '<a href="{}" style="{}">Editar con vista previa ↗</a>',
            reverse('panel_contenido:editor', args=[obj.clave]),
            estilo.replace('#417690', '#2e7d32')))
        return format_html(' '.join(['{}'] * len(enlaces)), *enlaces)

    @admin.action(description='Restaurar los textos originales (los del código)')
    def restaurar_textos_originales(self, request, queryset):
        actualizadas = queryset.update(textos={}, borrador={})
        self.message_user(
            request,
            f'{actualizadas} página(s) vuelven a servir los textos con los que se migraron.',
        )
