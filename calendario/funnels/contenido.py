# -*- coding: utf-8 -*-
"""Textos editables de las páginas de evento.

Las páginas que lista `/funnels/` —las tres pantallas de lanzamiento, sus
pantallas de gracias y las de campaña— tienen toda su copia declarada aquí:
qué textos lleva cada una, cómo se llaman en claro y de qué tipo son. Eso es lo
que el admin pinta como formulario, para que quien escribe los textos no tenga
que abrir ni una plantilla.

Cómo se resuelve un texto, en este orden:

1. `ContenidoDeEvento.textos` (BD) — lo que se haya guardado desde el admin.
2. La ficha de `evento_views` (código) — el valor con el que se migró la
   página desde Webflow.

Es decir: la BD manda, y el código es la red de seguridad. Si una página no
tiene fila, o la fila no trae un texto, se sirve el del código y la pantalla
sale igual que hoy. Por eso las fichas de `evento_views` siguen llevando la
copia entera: no son un residuo, son el valor por defecto.

Lo que NO se toca desde el admin vive solo en `evento_views`: plantilla,
colores, fotos, enlaces de WhatsApp, IDs de vídeo y códigos de funnel. Aquí
solo hay texto.

Convenio de resaltado: en un titular, `<strong>` es el resaltado de la marca
(el verde de Blocks, el azul de Finance, el degradado de la versión
paperboard…). Cada plantilla lo pinta con su estilo, así que basta con poner en
negrita lo que se quiera destacar.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Tuple


# ─── Tipos de campo ──────────────────────────────────────────────────────────
# Deciden qué widget pinta el admin y cómo se guarda el valor.
TEXTO = 'texto'   # una línea suelta (una chapa, un botón, un titular corto)
HTML = 'html'     # un párrafo; admite <strong>, <em>, <br>, <a>…
LISTA = 'lista'   # varias entradas, una por línea (los bullets)
GRUPO = 'grupo'   # varias fichas fijas con los mismos subcampos (las columnas)


@dataclass(frozen=True)
class Campo:
    """Un texto editable de una página."""

    clave: str
    etiqueta: str
    tipo: str = TEXTO
    ayuda: str = ''
    seccion: str = 'Contenido'
    # Solo GRUPO: cuántas fichas tiene y qué campos lleva cada una. El número es
    # fijo porque lo fija el diseño (tres columnas, dos variantes…): quien edita
    # cambia los textos, no cuántas cajas hay.
    filas: int = 0
    subcampos: Tuple['Campo', ...] = ()


@dataclass(frozen=True)
class Pagina:
    """Una página de evento y los textos que se le pueden editar."""

    clave: str
    nombre: str
    escuela: str
    tipo: str            # lanzamiento | gracias | campana
    campos: Tuple[Campo, ...]
    # Ruta relativa para el botón de vista previa del admin. Las que resuelven
    # la escuela por dominio necesitan además `?escuela=`, que se añade aquí.
    vista_previa: str = ''
    # Si la página tiene segunda versión (`?v=2`), para ofrecer las dos.
    tiene_v2: bool = False

    def url_publica(self, v2=False, borrador=False):
        """La URL con la que se ve esta página desde el panel.

        Las pantallas de lanzamiento y de gracias resuelven la marca por
        dominio; desde el dominio del panel hay que decírselo con `?escuela=`.
        """
        params = []
        if self.tipo in ('lanzamiento', 'gracias'):
            params.append(f'escuela={self.escuela}')
        if v2 and self.tiene_v2:
            params.append('v=2')
        if borrador:
            params.append('borrador=1')
        return self.vista_previa + ('?' + '&'.join(params) if params else '')


# ─── Trozos de esquema que se repiten ────────────────────────────────────────

AYUDA_HTML = ('Admite etiquetas HTML: &lt;strong&gt; negrita, &lt;em&gt; cursiva, '
              '&lt;u&gt; subrayado, &lt;br&gt; salto de línea y &lt;a href="…"&gt; enlace.')
AYUDA_RESALTE = ('Lo que envuelvas en &lt;strong&gt;…&lt;/strong&gt; se pinta con el color de '
                 'resalte de la página.')


def _pestana():
    return (
        Campo('titulo_pagina', 'Título de la pestaña del navegador',
              ayuda='No se ve en la página; es el nombre de la pestaña y el que sale en Google.',
              seccion='Pestaña del navegador'),
    )


def _formulario(telefono=True, legal=True, boton='Texto del botón de enviar'):
    """Los textos del formulario de registro: marcadores de posición y legal."""
    campos = [
        Campo('campo_nombre', 'Marcador del campo Nombre', seccion='Formulario de registro'),
        Campo('campo_email', 'Marcador del campo Email', seccion='Formulario de registro'),
    ]
    if telefono:
        campos.append(
            Campo('campo_telefono', 'Marcador del campo Teléfono', seccion='Formulario de registro'))
    if legal:
        campos += [
            Campo('legal_pre', 'Aviso legal (antes del enlace)', seccion='Formulario de registro'),
            Campo('legal_enlace', 'Texto del enlace a la política de privacidad',
                  seccion='Formulario de registro'),
        ]
    if boton:
        campos.append(Campo('cta', boton, seccion='Formulario de registro'))
    return tuple(campos)


def _gracias(titular_partido):
    """Las tres tarjetas de una pantalla de gracias.

    `titular_partido` distingue la maqueta de Blocks y Finance —el titular va en
    dos tramos, el primero en degradado— de la de Languages y la Trading Week,
    que lo llevan en una sola línea.
    """
    if titular_partido:
        titular = (
            Campo('titular_destacado', 'Titular · parte en color', seccion='Primera tarjeta'),
            Campo('titular_resto', 'Titular · resto', seccion='Primera tarjeta'),
        )
    else:
        titular = (Campo('titular', 'Titular', seccion='Primera tarjeta'),)
    return titular + (
        Campo('texto_1', 'Texto de la primera tarjeta', HTML, AYUDA_HTML, 'Primera tarjeta'),
        Campo('texto_2', 'Texto de la segunda tarjeta', HTML, AYUDA_HTML, 'Segunda tarjeta'),
        Campo('destacar_3', 'Titular de la tercera tarjeta', seccion='Tercera tarjeta'),
        Campo('texto_3', 'Texto de la tercera tarjeta', HTML, AYUDA_HTML, 'Tercera tarjeta'),
        Campo('cta', 'Texto del botón de WhatsApp', seccion='Botón'),
    ) + _pestana()


# ─── Esquema de cada página ──────────────────────────────────────────────────

# Pantallas de lanzamiento de Blocks y Finance (maqueta "paperboard": el
# formulario vive en una ventana que abre el CTA).
CAMPOS_LANZAMIENTO = (
    Campo('barra', 'Barra superior (fecha y hora del directo)', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('titulo_pre', 'Titular', HTML, 'La primera parte, sin color.', 'Cabecera'),
    Campo('titulo_grad', 'Titular · parte en degradado', ayuda='Se pinta con el degradado de la marca.',
          seccion='Cabecera'),
    Campo('subtitulo', 'Subtítulo', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('bullets', 'Bullets', LISTA,
          'Uno por línea. ' + AYUDA_HTML, 'Bullets'),
    Campo('cta', 'Texto del botón que abre el formulario', seccion='Bullets'),
    Campo('modal_titulo', 'Título de la ventana de registro', seccion='Ventana de registro'),
    Campo('modal_subtitulo', 'Texto de la ventana de registro', HTML, AYUDA_HTML,
          'Ventana de registro'),
) + _formulario(boton='') + (
    Campo('modal_cta', 'Texto del botón de enviar', seccion='Formulario de registro'),
) + _pestana()

# Pantalla de lanzamiento de Languages: mismo contenido, pero el titular se
# parte por el medio y el formulario va a la vista, sin ventana.
CAMPOS_LANZAMIENTO_LANGUAGES = (
    Campo('barra', 'Barra superior (fecha y hora del directo)', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('titulo_pre', 'Titular · antes del resalte', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('titulo_destacado', 'Titular · parte resaltada', seccion='Cabecera'),
    Campo('titulo_post', 'Titular · después del resalte', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('subtitulo', 'Subtítulo', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('bullets', 'Bullets', LISTA, 'Uno por línea. ' + AYUDA_HTML, 'Bullets'),
) + _formulario(legal=False, boton='Texto del botón de enviar') + _pestana()

CAMPOS_CODING_WEEK = (
    Campo('chapa_evento', 'Chapa · qué es', seccion='Cabecera'),
    Campo('chapa_fecha', 'Chapa · cuándo es', seccion='Cabecera'),
    Campo('titular', 'Titular', HTML, AYUDA_RESALTE, 'Cabecera'),
    Campo('subtitular', 'Subtítulo', HTML, AYUDA_HTML, 'Cabecera'),
) + _formulario() + (
    Campo('reclamo', 'Reclamo', HTML, AYUDA_RESALTE, 'Reclamo'),
    Campo('reclamo_detalle', 'Reclamo · detalle', HTML, AYUDA_HTML, 'Reclamo'),
    Campo('tarjetas', 'Tarjetas', GRUPO, seccion='Las dos tarjetas', filas=2, subcampos=(
        Campo('titulo', 'Título', HTML, AYUDA_RESALTE),
        Campo('texto_1', 'Primer párrafo', HTML, AYUDA_HTML),
        Campo('texto_2', 'Segundo párrafo', HTML, AYUDA_HTML),
    )),
    Campo('clase0_titulo', 'Título', HTML, AYUDA_RESALTE, 'Clase 0'),
    Campo('clase0_detalle', 'Detalle', HTML, AYUDA_HTML, 'Clase 0'),
    Campo('clase0_cartel', 'Cartel', HTML, AYUDA_HTML, 'Clase 0'),
    Campo('bio_titulo', 'Nombre del ponente', HTML, AYUDA_RESALTE, 'Ponente'),
    Campo('bio_parrafos', 'Biografía', LISTA, 'Un párrafo por línea. ' + AYUDA_HTML, 'Ponente'),
    Campo('cierre_antetitulo', 'Antetítulo', seccion='Cierre'),
    Campo('cierre_titulo', 'Titular', seccion='Cierre'),
    Campo('cierre_texto', 'Texto', HTML, AYUDA_HTML, 'Cierre'),
) + _pestana()

CAMPOS_TESTIMONIOS = (
    Campo('titular', 'Titular', HTML, AYUDA_RESALTE, 'Cabecera'),
    Campo('subtitular', 'Subtítulo', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('cta_texto', 'Texto del botón de agendar', seccion='Cabecera'),
    Campo('seccion_titulo', 'Título de la sección de testimonios', seccion='Testimonios'),
    Campo('sistema_titulo', 'Título de la sección', seccion='El sistema'),
    Campo('sistema_puntos', 'Puntos', LISTA, 'Uno por línea.', 'El sistema'),
    Campo('cierre_titulo', 'Titular', HTML, AYUDA_RESALTE, 'Cierre'),
    Campo('cierre_texto', 'Texto', HTML, AYUDA_HTML, 'Cierre'),
) + _pestana()

CAMPOS_BITACORA = (
    Campo('chapa', 'Chapa de la cabecera', seccion='Cabecera'),
    Campo('antetitulo', 'Antetítulo', seccion='Cabecera'),
    Campo('titular', 'Titular', HTML, AYUDA_HTML, 'Cabecera'),
    Campo('parrafos', 'Párrafos', LISTA, 'Uno por línea. ' + AYUDA_HTML, 'Cuerpo'),
) + _pestana()

CAMPOS_PILDORA = (
    Campo('chapa', 'Chapa de la cabecera', seccion='Cabecera'),
    Campo('numero', 'Número de la píldora', seccion='Cabecera'),
    Campo('titular', 'Titular', seccion='Cabecera'),
    Campo('cuerpo', 'Cuerpo', HTML, AYUDA_HTML, 'Cuerpo'),
    Campo('otras_titulo', 'Título de la sección', HTML, AYUDA_RESALTE, 'Las otras píldoras'),
    Campo('boton_tarjeta', 'Texto del botón de cada tarjeta', seccion='Las otras píldoras'),
    Campo('texto_tarjeta', 'Texto de la tarjeta que lleva a esta píldora',
          ayuda='Es el titular con el que las otras dos píldoras enlazan a esta.',
          seccion='Las otras píldoras'),
) + _pestana()

CAMPOS_TRADING_WEEK = (
    Campo('aviso', 'Chapa · qué es', seccion='Cabecera'),
    Campo('fecha', 'Chapa · cuándo es', seccion='Cabecera'),
    Campo('variantes', 'Titulares del test A/B', GRUPO,
          seccion='Titulares (test A/B)', filas=2, subcampos=(
              Campo('titular', 'Titular', HTML, AYUDA_RESALTE),
              Campo('subtitular', 'Subtítulo', HTML, AYUDA_RESALTE),
          )),
) + _formulario(telefono=False) + (
    Campo('curso_titulo', 'Título de la sección', HTML, AYUDA_RESALTE, 'El evento'),
    Campo('curso_bajada', 'Bajada', HTML, AYUDA_HTML, 'El evento'),
    Campo('columnas', 'Las tres columnas', GRUPO, seccion='El evento', filas=3, subcampos=(
        Campo('titulo', 'Título', HTML, AYUDA_HTML),
        Campo('texto', 'Texto', HTML, AYUDA_HTML),
    )),
    Campo('cta_secundario', 'Texto de los botones que suben al formulario', seccion='El evento'),
    Campo('taller_titulo', 'Título de la sección', HTML, AYUDA_RESALTE, 'Mini taller'),
    Campo('taller_bajada', 'Bajada', HTML, AYUDA_HTML, 'Mini taller'),
    Campo('pildoras', 'Las tres píldoras', LISTA, 'Una por línea.', 'Mini taller'),
    Campo('perfil_titulo', 'Nombre del ponente', HTML, AYUDA_RESALTE, 'Ponente'),
    Campo('perfil', 'Biografía', HTML, AYUDA_HTML, 'Ponente'),
    Campo('cierre_antetitulo', 'Antetítulo', seccion='Cierre'),
    Campo('cierre_titulo', 'Titular', HTML, AYUDA_HTML, 'Cierre'),
    Campo('cierre', 'Texto', HTML, AYUDA_HTML, 'Cierre'),
) + _pestana()


# ─── Registro de páginas ─────────────────────────────────────────────────────
# El orden es el de la tabla de `/funnels/`: primero los tres lanzamientos con
# sus pantallas de gracias, después las páginas de campaña.

PAGINAS = {
    p.clave: p for p in (
        Pagina('lanzamiento-blocks', 'Evento en directo · Conquer Blocks', 'conquer-blocks',
               'lanzamiento', CAMPOS_LANZAMIENTO, '/evento/evento-online'),
        Pagina('lanzamiento-finance', 'Evento en directo · Conquer Finance', 'conquer-finance',
               'lanzamiento', CAMPOS_LANZAMIENTO, '/evento/evento-online'),
        Pagina('lanzamiento-languages', 'Evento en directo · Conquer Languages',
               'conquer-languages', 'lanzamiento', CAMPOS_LANZAMIENTO_LANGUAGES, '/cl-evento'),
        Pagina('gracias-blocks', 'Gracias · Conquer Blocks', 'conquer-blocks', 'gracias',
               _gracias(titular_partido=True), '/evento/gracias-comunidad'),
        Pagina('gracias-finance', 'Gracias · Conquer Finance', 'conquer-finance', 'gracias',
               _gracias(titular_partido=True), '/evento/gracias-comunidad'),
        Pagina('gracias-languages', 'Gracias · Conquer Languages', 'conquer-languages', 'gracias',
               _gracias(titular_partido=False), '/grupos-comunidad'),
        Pagina('gracias-trading-week', 'Gracias · Trading Week', 'conquer-finance', 'gracias',
               _gracias(titular_partido=False), '/grupos-comunidad', tiene_v2=True),
        Pagina('coding-week', 'Coding Week', 'conquer-blocks', 'campana', CAMPOS_CODING_WEEK,
               '/evento/evento-coding-week-eu', tiene_v2=True),
        Pagina('testimonios', 'Testimonios', 'conquer-blocks', 'campana', CAMPOS_TESTIMONIOS,
               '/evento/evento-testimonios', tiene_v2=True),
        Pagina('bitacora', 'Bitácora · La Clase 0', 'conquer-languages', 'campana',
               CAMPOS_BITACORA, '/eventos/bitacora'),
        Pagina('pildora-1', 'Píldora 1 · Trading Week', 'conquer-finance', 'campana',
               CAMPOS_PILDORA, '/evento/pildoras-evento-1', tiene_v2=True),
        Pagina('pildora-2', 'Píldora 2 · Trading Week', 'conquer-finance', 'campana',
               CAMPOS_PILDORA, '/evento/pildoras-evento-2', tiene_v2=True),
        Pagina('pildora-3', 'Píldora 3 · Trading Week', 'conquer-finance', 'campana',
               CAMPOS_PILDORA, '/evento/pildoras-evento-3', tiene_v2=True),
        Pagina('trading-week', 'Registro Trading Week', 'conquer-finance', 'campana',
               CAMPOS_TRADING_WEEK, '/trading-week-2025', tiene_v2=True),
    )
}


# ─── Resolución: código + BD ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _fichas_del_codigo():
    """Índice clave → ficha de `evento_views`, que trae los valores por defecto.

    El import va aquí dentro y no arriba porque `evento_views` importa este
    módulo: al revés se enredarían.
    """
    from .evento_views import EVENTOS, GRACIAS, GRACIAS_TRADING_WEEK, PAGINAS_DE_CAMPANA

    fichas = {}
    for ficha in (*EVENTOS.values(), *GRACIAS.values(), GRACIAS_TRADING_WEEK,
                  *PAGINAS_DE_CAMPANA.values()):
        fichas[ficha['clave']] = ficha
    return fichas


def campos_de(clave):
    pagina = PAGINAS.get(clave)
    return pagina.campos if pagina else ()


def defectos_de(clave):
    """Los textos con los que la página se migró: los del código."""
    ficha = _fichas_del_codigo().get(clave, {})
    return {campo.clave: ficha.get(campo.clave) for campo in campos_de(clave)}


def guardados_de(clave, borrador=False):
    """Lo que hay guardado para esa página.

    Con `borrador=True` se devuelve lo que se está escribiendo y todavía no ha
    publicado nadie —lo que enseña la vista previa—; si no hay borrador abierto,
    lo publicado.
    """
    from .models import ContenidoDeEvento

    fila = ContenidoDeEvento.objects.filter(clave=clave).first()
    if not fila:
        return {}
    if borrador and fila.borrador:
        return dict(fila.borrador)
    return dict(fila.textos or {})


def valores_de(clave, borrador=False):
    """Los textos que se ven de verdad: los del código con la BD encima."""
    valores = defectos_de(clave)
    guardados = guardados_de(clave, borrador=borrador)
    for campo in campos_de(clave):
        if campo.clave in guardados:
            valores[campo.clave] = guardados[campo.clave]
    return valores


def con_textos(ficha, borrador=False):
    """La ficha del código con los textos guardados por encima.

    Es lo único que llaman las vistas. Devuelve una copia: las fichas de
    `evento_views` son de módulo y se comparten entre peticiones, así que no se
    tocan nunca.

    `borrador=True` lo pide la vista previa del panel (ver `views_panel`), y
    solo se lo concede a quien puede editar: con eso la página se pinta con lo
    que aún no ha publicado nadie.
    """
    clave = ficha.get('clave')
    if not clave:
        return ficha
    guardados = guardados_de(clave, borrador=borrador)
    salida = dict(ficha)
    for campo in campos_de(clave):
        if campo.clave not in guardados:
            continue
        valor = guardados[campo.clave]
        if campo.tipo == GRUPO:
            salida[campo.clave] = _mezcla_grupo(ficha.get(campo.clave) or (), valor)
        else:
            salida[campo.clave] = valor
    # Las píldoras se enseñan tarjetas entre ellas: el titular de cada tarjeta
    # es el que se edita en la página a la que lleva, no aquí.
    if salida.get('tarjetas') and all(isinstance(t, dict) and t.get('clave')
                                      for t in salida['tarjetas']):
        salida['tarjetas'] = tuple(
            {**t, 'texto': (valores_de(t['clave'], borrador=borrador).get('texto_tarjeta')
                            or t.get('texto', ''))}
            for t in salida['tarjetas']
        )
    return salida


def _mezcla_grupo(base, guardado):
    """Une las fichas de un GRUPO: el texto guardado, el resto del código.

    Cada ficha lleva cosas que no se editan (la imagen de la columna, la letra
    de la variante A/B), así que se parte de la del código y solo se pisan los
    textos que vengan de la BD. Se respeta el número de fichas del diseño: si en
    la BD hay de más, sobran; si hay de menos, esas se quedan como estaban.
    """
    if not isinstance(guardado, list):
        return tuple(base)
    fichas = []
    for i, item in enumerate(base):
        nueva = dict(item)
        if i < len(guardado) and isinstance(guardado[i], dict):
            nueva.update({k: v for k, v in guardado[i].items() if v is not None})
        fichas.append(nueva)
    return tuple(fichas)


# ─── Del formulario al JSON y al revés ───────────────────────────────────────
# Lo usan las dos pantallas que editan esto (el admin y la del panel), así que
# vive aquí y no en ninguna de las dos.

import re  # noqa: E402  (al final: solo lo necesita esta sección)


# Lo que no se admite dentro de un texto. Son páginas públicas y estos campos se
# pintan tal cual (sin escapar), así que se corta lo que podría ejecutar código;
# el HTML de maquetado —negritas, saltos, enlaces— pasa sin problema.
HTML_PROHIBIDO = re.compile(
    r'<\s*(script|iframe|object|embed|form)\b|javascript\s*:|\son[a-z]+\s*=',
    re.IGNORECASE,
)

ERROR_HTML = ('Ese texto lleva HTML que no se admite (scripts, iframes, formularios o '
              'atributos "on…"). Puedes usar &lt;strong&gt;, &lt;em&gt;, &lt;u&gt;, '
              '&lt;br&gt;, &lt;span&gt; y enlaces.')


def html_valido(valor):
    return not (valor and HTML_PROHIBIDO.search(valor))


def nombre_campo(campo, indice=None, subcampo=None):
    """Nombre del campo en el formulario. Los GRUPO se aplanan por posición."""
    if subcampo is None:
        return f'txt__{campo.clave}'
    return f'txt__{campo.clave}__{indice}__{subcampo.clave}'


def a_formulario(clave, valores):
    """{clave del campo: valor} → {nombre en el formulario: texto escrito}."""
    plano = {}
    for campo in campos_de(clave):
        if campo.tipo == GRUPO:
            fichas = valores.get(campo.clave) or ()
            for i in range(campo.filas):
                ficha = fichas[i] if i < len(fichas) else {}
                for sub in campo.subcampos:
                    plano[nombre_campo(campo, i, sub)] = ficha.get(sub.clave) or ''
        elif campo.tipo == LISTA:
            plano[nombre_campo(campo)] = '\n'.join(valores.get(campo.clave) or [])
        else:
            plano[nombre_campo(campo)] = valores.get(campo.clave) or ''
    return plano


def desde_formulario(clave, datos):
    """{nombre en el formulario: texto} → el JSON que se guarda.

    Un campo vacío NO se guarda: esa página vuelve a servir el texto original en
    ese hueco. Es la red de seguridad de todo esto —borrar por accidente el
    titular de una landing y dejarla muda sería el fallo más fácil de cometer y
    el más caro—, y de paso da una forma evidente de deshacer un cambio: se
    vacía la caja y vuelve lo que había.
    """
    textos = {}
    for campo in campos_de(clave):
        if campo.tipo == GRUPO:
            fichas = []
            for i in range(campo.filas):
                fichas.append({
                    sub.clave: (datos.get(nombre_campo(campo, i, sub)) or '').strip()
                    for sub in campo.subcampos
                    if (datos.get(nombre_campo(campo, i, sub)) or '').strip()
                })
            if any(fichas):
                textos[campo.clave] = fichas
        elif campo.tipo == LISTA:
            entradas = [l.strip() for l in (datos.get(nombre_campo(campo)) or '').splitlines()
                        if l.strip()]
            if entradas:
                textos[campo.clave] = entradas
        else:
            valor = (datos.get(nombre_campo(campo)) or '').strip()
            if valor:
                textos[campo.clave] = valor
    return textos


def errores_de_html(clave, datos):
    """Los campos del formulario cuyo HTML no se admite."""
    return [nombre for nombre, valor in datos.items()
            if nombre.startswith('txt__') and isinstance(valor, str) and not html_valido(valor)]


def puede_ver_borrador(request):
    """Si a esta petición se le puede enseñar el borrador en vez de lo publicado.

    Lo pide la vista previa del panel con `?borrador=1`, y solo se le concede a
    quien puede editar los textos: en una página pública, un borrador a medias
    no lo tiene que ver nadie de fuera.
    """
    if not request.GET.get('borrador'):
        return False
    usuario = getattr(request, 'user', None)
    return bool(usuario and usuario.is_authenticated
                and usuario.tiene_permiso('contenido_eventos.editar'))
