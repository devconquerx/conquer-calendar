# -*- coding: utf-8 -*-
"""`{% imagen %}`: la URL de una imagen de una página de evento.

Las imágenes de estas páginas tienen dos procedencias:

- las que vinieron con la migración, que son ficheros del repo y se sirven por
  `{% static %}` (`img/eventos/…`);
- las que sube quien edita la página desde el panel, que van a `MEDIA_ROOT` y
  se sirven por `/media/…` (nginx las sirve desde el volumen del host, así que
  sobreviven a los despliegues).

La plantilla no tiene por qué saber cuál es cuál: pinta `{% imagen ... %}` y
esto resuelve. Cualquier valor que ya sea una URL —empieza por `/media/`,
`http` o `//`— se devuelve tal cual; el resto se trata como ruta de estáticos.
"""
from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def imagen(valor):
    if not valor:
        return ''
    valor = str(valor)
    if valor.startswith(('/media/', 'http://', 'https://', '//', 'data:')):
        return valor
    return static(valor)
