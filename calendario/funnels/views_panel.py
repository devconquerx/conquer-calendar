# -*- coding: utf-8 -*-
"""Pantalla del panel para escribir los textos de las páginas de evento.

Es la puerta buena para quien escribe la copia: a la izquierda una caja por
texto con resaltado de HTML, a la derecha la página de verdad. Lo que se guarda
va a `borrador` y solo se ve en esa vista previa; la página pública no cambia
hasta pulsar Publicar.

El admin de Django sigue teniendo su formulario (ver `admin.py`), pero allí
guardar publica de una vez.
"""
import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from calendario.permisos.decorators import requiere_permiso
from calendario.permisos.mixins import RequierePermisoMixin

from . import contenido
from .models import ContenidoDeEvento


TIPOS = {'lanzamiento': 'Pantalla de lanzamiento', 'gracias': 'Pantalla de gracias',
         'campana': 'Página de campaña'}


class ListaDePaginasView(RequierePermisoMixin, TemplateView):
    """Las páginas de evento con su estado: publicada, con borrador o sin tocar."""

    permiso_requerido = 'contenido_eventos.ver'
    template_name = 'pages/panel/contenido/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filas = {f.clave: f for f in ContenidoDeEvento.objects.all()}
        # El orden es el del registro, que es el de la tabla de /funnels/.
        ctx['paginas'] = [
            {
                'pagina': pagina,
                'fila': filas.get(clave),
                'tipo': TIPOS.get(pagina.tipo, pagina.tipo),
                'editada': bool(filas[clave].textos) if clave in filas else False,
                'con_borrador': (filas[clave].hay_cambios_sin_publicar
                                 if clave in filas else False),
                'publicado_en': filas[clave].publicado_en if clave in filas else None,
                'publicado_por': filas[clave].publicado_por if clave in filas else None,
                'url_editor': reverse('panel_contenido:editor', args=[clave]),
                'url_publica': pagina.url_publica(),
            }
            for clave, pagina in contenido.PAGINAS.items()
        ]
        return ctx


class EditorView(RequierePermisoMixin, TemplateView):
    """El editor de una página: cajas de texto a la izquierda, página a la derecha."""

    permiso_requerido = 'contenido_eventos.ver'
    template_name = 'pages/panel/contenido/editor.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        clave = self.kwargs['clave']
        pagina = contenido.PAGINAS.get(clave)
        if not pagina:
            raise Http404('No hay ninguna página de evento con esa clave')
        fila = get_object_or_404(ContenidoDeEvento, clave=clave)

        # Lo que se enseña al abrir: el borrador si lo hay; si no, lo publicado;
        # y donde no haya nada, el texto con el que se migró la página.
        escritos = contenido.a_formulario(clave, contenido.valores_de(clave, borrador=True))
        publicados = contenido.a_formulario(clave, contenido.valores_de(clave))

        secciones = []
        for campo in pagina.campos:
            if not secciones or secciones[-1]['nombre'] != campo.seccion:
                existente = next((s for s in secciones if s['nombre'] == campo.seccion), None)
                if existente:
                    seccion = existente
                else:
                    seccion = {'nombre': campo.seccion, 'campos': []}
                    secciones.append(seccion)
            else:
                seccion = secciones[-1]
            if campo.tipo == contenido.GRUPO:
                for i in range(campo.filas):
                    for sub in campo.subcampos:
                        nombre = contenido.nombre_campo(campo, i, sub)
                        seccion['campos'].append(self._campo(
                            nombre, f'{campo.etiqueta.rstrip("s")} {i + 1} · {sub.etiqueta}',
                            sub, escritos, publicados))
            else:
                nombre = contenido.nombre_campo(campo)
                seccion['campos'].append(
                    self._campo(nombre, campo.etiqueta, campo, escritos, publicados))

        ctx.update({
            'pagina': pagina,
            'fila': fila,
            'tipo': TIPOS.get(pagina.tipo, pagina.tipo),
            'secciones': secciones,
            'puede_editar': self.request.user.tiene_permiso('contenido_eventos.editar'),
            'url_preview': pagina.url_publica(borrador=True),
            'url_preview_v2': pagina.url_publica(v2=True, borrador=True) if pagina.tiene_v2 else '',
            'url_publica': pagina.url_publica(),
            'url_guardar': reverse('panel_contenido:guardar', args=[pagina.clave]),
            'url_publicar': reverse('panel_contenido:publicar', args=[pagina.clave]),
            'url_descartar': reverse('panel_contenido:descartar', args=[pagina.clave]),
            'ayuda_html': contenido.AYUDA_HTML,
        })
        return ctx

    @staticmethod
    def _campo(nombre, etiqueta, campo, escritos, publicados):
        valor = escritos.get(nombre, '')
        return {
            'nombre': nombre,
            'etiqueta': etiqueta,
            'ayuda': campo.ayuda,
            'tipo': campo.tipo,
            'valor': valor,
            # Para marcar en el editor lo que cambia respecto a lo publicado.
            'publicado': publicados.get(nombre, ''),
            'lineas': min(12, max(2, valor.count('\n') + 1 + (1 if len(valor) > 90 else 0))),
        }


def _fila_o_404(clave):
    if clave not in contenido.PAGINAS:
        raise Http404('No hay ninguna página de evento con esa clave')
    return get_object_or_404(ContenidoDeEvento, clave=clave)


def _textos_del_post(request, clave):
    """Los textos que manda el editor, ya en la forma en que se guardan."""
    datos = json.loads(request.body or '{}') if request.content_type == 'application/json' \
        else request.POST.dict()
    errores = contenido.errores_de_html(clave, datos)
    return contenido.desde_formulario(clave, datos), errores


@require_POST
@requiere_permiso('contenido_eventos.editar')
def guardar_borrador(request, clave):
    """Guarda lo escrito como borrador. No toca la página pública."""
    fila = _fila_o_404(clave)
    textos, errores = _textos_del_post(request, clave)
    if errores:
        return JsonResponse({'ok': False, 'errores': errores, 'mensaje': contenido.ERROR_HTML},
                            status=400)
    fila.borrador = textos
    fila.save(update_fields=['borrador', 'actualizado_en'])
    return JsonResponse({'ok': True, 'sin_publicar': fila.hay_cambios_sin_publicar})


@require_POST
@requiere_permiso('contenido_eventos.editar')
def publicar(request, clave):
    """Pasa el borrador a la página pública."""
    fila = _fila_o_404(clave)
    textos, errores = _textos_del_post(request, clave)
    if errores:
        return JsonResponse({'ok': False, 'errores': errores, 'mensaje': contenido.ERROR_HTML},
                            status=400)
    # Se publica lo que hay en pantalla, no lo último que se guardó: si alguien
    # escribe y le da a Publicar sin guardar antes, publica lo que está viendo.
    fila.borrador = textos
    fila.publicar(usuario=request.user)
    return JsonResponse({
        'ok': True,
        'publicado_en': fila.publicado_en.isoformat(),
        'mensaje': 'Publicado. La página ya sirve estos textos.',
    })


@require_POST
@requiere_permiso('contenido_eventos.editar')
def descartar_borrador(request, clave):
    """Tira lo escrito y deja la página como está publicada."""
    fila = _fila_o_404(clave)
    fila.descartar_borrador()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('panel_contenido:editor', clave=clave)
