from django.contrib import admin

from .models import VideoEspejo


@admin.register(VideoEspejo)
class VideoEspejoAdmin(admin.ModelAdmin):
    list_display = ['guid', 'library_nombre', 'titulo', 'estado', 'resolucion', 'mb', 'copiado_en']
    list_filter = ['estado', 'library_nombre', 'resolucion']
    search_fields = ['guid', 'titulo', 'library_id']
    readonly_fields = [f.name for f in VideoEspejo._meta.fields]
    ordering = ['-copiado_en']

    @admin.display(description='Tamaño')
    def mb(self, obj):
        return f'{obj.bytes_copiados / 1e6:.0f} MB' if obj.bytes_copiados else '—'

    def has_add_permission(self, request):
        return False
