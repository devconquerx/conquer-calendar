from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.views import View
from django.http import HttpResponse

from .models import PlantillaCorreo


_VARS_DEMO = {
    '{{nombre_invitado}}':     'María García',
    '{{email_invitado}}':      'maria.garcia@ejemplo.com',
    '{{telefono_invitado}}':   '+57 300 123 4567',
    '{{nombre_host}}':         'Carlos Rodríguez',
    '{{email_host}}':          'carlos.rodriguez@conquerx.com',
    '{{nombre_evento}}':       'Consultoría estratégica 45 min',
    '{{fecha_hora}}':          'Jue 15 de jun 2026 · 10:30 – 11:15',
    '{{fecha_hora_invitado}}': 'Jue 15 de jun 2026 · 10:30 – 11:15',
    '{{fecha_hora_host}}':     'Jue 15 de jun 2026 · 08:30 – 09:15',
    '{{fecha_hora_utc}}':      '15:30 UTC',
    '{{timezone}}':            'America/Bogota',
    '{{timezone_host}}':       'America/Bogota',
    '{{duracion}}':            '45',
    '{{google_meet_url}}':     'https://meet.google.com/abc-defg-hij',
    '{{google_event_url}}':    'https://calendar.google.com/calendar/event?eid=demo',
    '{{link_reserva}}':        'http://localhost:8002/panel/reservas/1/',
    '{{link_cancelar}}':       '#',
}


def _render_demo(texto):
    for var, valor in _VARS_DEMO.items():
        texto = texto.replace(var, valor)
    return texto


class PlantillaCorreoPreviewView(LoginRequiredMixin, View):

    def get(self, request, pk):
        plantilla = get_object_or_404(PlantillaCorreo, pk=pk)

        logo_url = None
        if plantilla.logo:
            try:
                logo_url = request.build_absolute_uri(plantilla.logo.url)
            except Exception:
                logo_url = None

        default_logo_url = request.build_absolute_uri(static('correos/conquerx-logo.png'))

        campos = set(v.strip('{}') for v in (plantilla.campos_visibles or []))

        html = render_to_string('correos/base.html', {
            'logo_url': logo_url,
            'default_logo_url': default_logo_url,
            'color_encabezado': plantilla.color_encabezado or '#111827',
            'texto_encabezado': _render_demo(plantilla.texto_encabezado),
            'cuerpo': _render_demo(plantilla.cuerpo),
            'pie_pagina': plantilla.pie_pagina,
            'campos': campos,
            **{k.strip('{}'): v for k, v in _VARS_DEMO.items()},
        })

        return HttpResponse(html)
