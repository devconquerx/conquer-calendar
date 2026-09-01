# -*- coding: utf-8 -*-
"""Pantallas de evento (lanzamiento) de cada marca.

Son páginas informativas: presentan el directo y recogen el registro en un
popup. No cuelgan de un `FunnelForm` —no tienen StepForm, ni scoring, ni
reserva— así que viven aparte del resto de vistas de funnels y su contenido se
edita aquí, que es lo que cambia en cada edición del evento (fecha, titular y
bullets).

Réplica de www.conquerblocks.com/evento/evento-online, que hasta ahora servía
Webflow y mandaba los registros a Make.
"""
import random

from django.conf import settings
from django.http import Http404
from django.utils.cache import patch_vary_headers
from django.views.generic import TemplateView

from . import consentimiento as consent
from .contenido import con_textos, puede_ver_borrador
from .context_processors import get_gtm_config
from .views import _base_path, _escuela_por_host


# Contenido por escuela. Lo que cambia entre ediciones es `barra` (fecha y hora)
# y, si acaso, el titular; el resto se mantiene.
# `publicada` dice si la ruta real de la página ya existe en Cloudflare. Las
# tres pantallas de lanzamiento y sus pantallas de gracias sí; las de campaña
# todavía no, así que en producción solo se llega a ellas por el prefijo
# `/preview` del Worker. Lo usa el panel de /funnels/ para enlazar a donde de
# verdad responden. Al dar de alta la ruta buena, se pone a True aquí.
EVENTOS = {
    'conquer-blocks': {
        # `orden` es el turno en que se migró desde Webflow. Solo lo usa el
        # panel de /funnels/, que lista todas las páginas de evento juntas en
        # ese orden: es el hilo por el que se han ido revisando, y ordenarlas
        # por escuela o alfabéticamente lo rompía.
        'clave': 'lanzamiento-blocks',
        'orden': 1,
        'publicada': True,
        'plantilla': 'pages/public/evento/paperboard.html',
        'marca': 'Conquer Blocks',
        'gradiente_1': '#ffbf00',
        'gradiente_2': '#ff4000',
        'logo': 'img/eventos/cb-logo-horizontal-blanco.png',
        'logo_ancho': 316,
        'foto': 'img/eventos/cb-bienvenido-live.jpg',
        'foto_borde': '1.5px solid #f70',
        'hueco': '1rem',
        # Código de la edición con el que el CRM indexa estos leads. Es solo
        # el valor de reserva: normalmente lo manda la campaña (ver
        # `_funnel_de_la_edicion`), y este se usa cuando no viene ninguna.
        'funnel': 'cb-lanzamiento11',
        'titulo_pagina': 'Evento Online Simple',
        'barra': 'EVENTO EN DIRECTO : Domingo 16 de Agosto a las 19:00 de Madrid '
                 '(14:00 de Buenos Aires, 13:00 de Miami)',
        'titulo_pre': 'Descubre cómo acceder a la profesión con mayor demanda este 2026, '
                      'trabajo remoto y sin techo salarial, consiguiendo tu primer empleo como ',
        'titulo_grad': 'Desarrollador Full Stack en menos de 12 meses',
        'subtitulo': 'Sin experiencia previa y sin dejar tu trabajo mientras aprendes',
        'bullets': [
            'Descubrirás por qué la IA ha hecho que <strong>aprender a programar sea más fácil</strong> '
            'que nunca y cómo aprovecharlo aunque partas desde cero',
            'Entenderás la situación real del <strong>mercado laboral tech en 2026</strong> y por qué '
            'la demanda de desarrolladores no para de crecer',
            'Conocerás <strong>personas normales</strong>, sin experiencia previa y sin dejar sus '
            'trabajos, que han dado el salto en meses — <strong>no en años</strong>',
            'Aprenderás el método exacto que seguimos en <strong>Conquer Blocks</strong> para entrar '
            'al sector tech con garantía de empleo',
        ],
        'cta': 'Asistir al directo',
        'modal_titulo': 'Regístrate gratis ahora',
        'modal_subtitulo': 'Recuerda que al final podrás hablar personalmente con nosotros '
                           'para resolver cualquier duda.',
        'modal_cta': 'Regístrate gratis ahora',
        'legal_pre': 'Al continuar, confirmas que has leído y aceptas nuestra',
        'legal_enlace': 'política de privacidad.',
        'politica_url': 'https://www.conquerblocks.com/politica-de-privacidad',
        # Marcadores de posición del formulario, editables como el resto de la
        # copia: los pinta la plantilla desde la ficha.
        'campo_nombre': 'Introduce tu nombre',
        'campo_email': 'Tu mejor email',
        'campo_telefono': 'Número de WhatsApp',
    },
    'conquer-finance': {
        'clave': 'lanzamiento-finance',
        'orden': 2,
        'publicada': True,
        # Misma maqueta que Blocks: en Webflow son la misma página con otra
        # marca. Cambian el degradado (verde), el logo, la foto y la copia.
        'plantilla': 'pages/public/evento/paperboard.html',
        'titulo_pagina': 'Evento en Directo: Trading sin Riesgo | Conquer Finance',
        'ruta': 'evento/evento-online',
        'funnel': 'cf-lanzamiento11',
        # Sí, la de Blocks: es a donde manda el original. No es un descuido al
        # copiar la página —`conquerfinance.com/grupos-comunidad` existe pero
        # está a medias, con Lorem Ipsum—, así que Finance no tiene una propia.
        'marca': 'Conquer Finance',
        'gradiente_1': '#aed916',
        'gradiente_2': '#3ac043',
        'titular_1': '#3ac043',
        'titular_2': '#aed916',
        'logo': 'img/eventos/cf-logo-horizontal-blanco.png',
        'logo_ancho': 338,
        'foto': 'img/eventos/cf-evento-imagen.webp',
        'foto_borde': '2px solid #3ac043',
        # Finance separa más los bloques de la tarjeta que Blocks.
        'hueco': '28px',
        'barra': 'EVENTO EN DIRECTO : Domingo 12 de julio a las 19:00 de Madrid '
                 '(14:00 de Buenos Aires, 13:00 de Miami)',
        'titulo_pre': 'Aprende Cómo generar +2.000 \u20ac al mes con trading siguiendo un sistema '
                      'claro que cientos de personas ya han usado este 2025',
        'titulo_grad': '',
        'subtitulo': 'el paso a paso para conseguirlo Sin arriesgar tu propio capital y sin '
                     'necesidad de experiencia previa',
        'bullets': [
            'Descubrir\u00e1s por qu\u00e9 el <strong>Trading Institucional</strong> hace que operar sin '
            'arriesgar tus ahorros sea posible y c\u00f3mo lograrlo aunque partas desde cero',
            'Entender\u00e1s la situaci\u00f3n real de los <strong>mercados financieros en 2026</strong> y '
            'por qu\u00e9 el acceso a capital privado no para de crecer',
            'Conocer\u00e1s <strong>personas normales</strong>, sin experiencia previa y sin dejar sus '
            'empleos, que generan de 2.000\u20ac a 5.000\u20ac/mes en semanas \u2014 <strong>no en a\u00f1os</strong>',
            'Aprender\u00e1s el m\u00e9todo exacto que seguimos en <strong>Conquer Finance</strong> para '
            'operar fondos de inversi\u00f3n sin riesgo de capital',
        ],
        'cta': 'Asistir al directo',
        'modal_titulo': 'Reg\u00edstrate gratis ahora',
        'modal_subtitulo': 'Recuerda que al final podr\u00e1s hablar personalmente con nosotros '
                           'para resolver cualquier duda.',
        'modal_cta': 'Reg\u00edstrate gratis ahora',
        'legal_pre': 'Al continuar, confirmas que has le\u00eddo y aceptas nuestra',
        'legal_enlace': 'pol\u00edtica de privacidad.',
        'politica_url': 'https://www.conquerfinance.com/politica-de-privacidad',
        # Marcadores de posición del formulario, editables como el resto de la
        # copia: los pinta la plantilla desde la ficha.
        'campo_nombre': 'Introduce tu nombre',
        'campo_email': 'Tu mejor email',
        'campo_telefono': 'Número de WhatsApp',
    },
    'conquer-languages': {
        'clave': 'lanzamiento-languages',
        'orden': 3,
        'publicada': True,
        'plantilla': 'pages/public/evento/languages.html',
        'titulo_pagina': 'English Event',
        'ruta': 'cl-evento',
        # Languages sí lo lleva fijo en la página (no lo saca de la campaña),
        # pero se acepta igual la campaña por coherencia. Edición en curso.
        'funnel': 'cl-lanzamiento9',
        'barra': 'De 0 a inglés fluido en 90 días: El 6 de Septiembre a las 19:00 Madrid '
                 '(14:00 de Buenos Aires, 13:00 de Miami)',
        # El titular parte el destacado por el medio, no al final como el de
        # Blocks, así que va en tres tramos.
        'titulo_pre': 'Descubre por qué tu cerebro Bloquea el inglés (y cómo Desbloquearlo '
                      'para hablar de forma fluida ',
        'titulo_destacado': 'en menos de 90 días',
        'titulo_post': ') aunque lleves años intentando aprender sin resultado',
        'subtitulo': 'La clase gratuita donde descubrirás por qué esta vez será diferente',
        'bullets': [
            'Descubrirás cómo <strong>añadir valor a tu carrera profesional y ganar más</strong> '
            'gracias a únicamente adquirir un nivel de inglés por encima de la media.',
            'Conocerás por dentro <strong>nuestra metodología única y dinámica</strong> con la que '
            'nuestros alumnos consiguen un B2 en menos de 90 días.',
        ],
        'cta': 'Regístrate gratis ahora',
        # A diferencia de Blocks, aquí el consentimiento es una casilla
        # obligatoria, no un texto informativo.
        'consentimiento': 'He leído y acepto la',
        'politica_texto': 'política de privacidad*',
        'politica_url': 'https://www.conquerlanguages.com/politica-de-privacidad',
        # Marcadores de posición del formulario, editables como el resto de la
        # copia: los pinta la plantilla desde la ficha.
        'campo_nombre': 'Introduce tu nombre',
        'campo_email': 'Tu mejor email',
        'campo_telefono': 'Número de WhatsApp',
    },
}


# Página de "gracias": el último paso real del registro. Presenta el grupo de
# WhatsApp de asistentes, y a los 15 segundos salta sola a él.
#
# En Webflow, la de Finance manda al grupo de Blocks —las tres veces— porque su
# página se clonó de la de Blocks y nadie cambió el enlace. Aquí se deja igual
# de momento para no inventarse un grupo que no existe: cambiar `whatsapp` por
# el enlace bueno es lo único que hace falta cuando lo haya.
GRACIAS = {
    'conquer-blocks': {
        'plantilla': 'pages/public/evento/gracias-paperboard.html',
        'publicada': True,
        'ruta': 'evento/gracias-comunidad',
        'titulo_pagina': 'Gracias Comunidad',
        'clave': 'gracias-blocks',
        # Los textos de las tres tarjetas. Estaban escritos en la plantilla, que
        # es común a las dos marcas; aquí cada una lleva los suyos y se pueden
        # editar por separado desde el admin.
        'titular_destacado': '¡OBLIGATORIO!',
        'titular_resto': 'Queda un último paso para reservar tu entrada...',
        'texto_1': 'Hemos creado una comunidad VIP en WhatsApp para todos los asistentes a la '
                   '<strong>Clase Privada de Conquer Blocks.</strong><br>'
                   'Es de vital importancia que te unas para confirmar tu asistencia.',
        'texto_2': 'Dale al botón de abajo para unirte totalmente gratis al grupo exclusivo '
                   'del Evento ⬇️',
        'destacar_3': '<strong>¿Miras más tu Whatsapp que tu e-mail?</strong>',
        'texto_3': 'Tranquilo, a mucha gente de nuestra comunidad le ocurre.<br>'
                   'Por eso, hemos creado una comunidad de WhatsApp, donde recibirás todas las '
                   'comunicaciones del Evento, y mucho valor adicional de Conquer Blocks.',
        'whatsapp': 'https://cb.conquerx.com/1Qt1ef/',
        'cta': 'Unirme a la Comunidad VIP de WhatsApp',
        'icono_cta': True,
        'marca': 'Conquer Blocks',
        'logo': 'img/eventos/cb-logo-horizontal-blanco.png',
        'logo_ancho': 152,
        'gradiente_1': '#ff4000',
        'gradiente_2': '#ff9800',
        # El titular degradado (`.conquer-gradient`) no usa la misma pareja que
        # el CTA ni en el mismo orden, así que va aparte en cada marca.
        'titular_1': '#ff4000',
        'titular_2': '#ff9800',
    },
    'conquer-finance': {
        'plantilla': 'pages/public/evento/gracias-paperboard.html',
        'publicada': True,
        'ruta': 'evento/gracias-comunidad',
        'titulo_pagina': '¡Registro Confirmado! - Trading Week | Conquer Finance',
        'clave': 'gracias-finance',
        # Los textos de las tres tarjetas. Estaban escritos en la plantilla, que
        # es común a las dos marcas; aquí cada una lleva los suyos y se pueden
        # editar por separado desde el admin.
        'titular_destacado': '¡OBLIGATORIO!',
        'titular_resto': 'Queda un último paso para reservar tu entrada...',
        'texto_1': 'Hemos creado una comunidad VIP en WhatsApp para todos los asistentes a la '
                   '<strong>Clase Privada de Conquer Finance.</strong><br>'
                   'Es de vital importancia que te unas para confirmar tu asistencia.',
        'texto_2': 'Dale al botón de abajo para unirte totalmente gratis al grupo exclusivo '
                   'del Evento ⬇️',
        'destacar_3': '<strong>¿Miras más tu Whatsapp que tu e-mail?</strong>',
        'texto_3': 'Tranquilo, a mucha gente de nuestra comunidad le ocurre.<br>'
                   'Por eso, hemos creado una comunidad de WhatsApp, donde recibirás todas las '
                   'comunicaciones del Evento, y mucho valor adicional de Conquer Finance.',
        # OJO: es el grupo de Blocks, tal como está hoy en Webflow.
        'whatsapp': 'https://cb.conquerx.com/1Qt1ef/',
        'cta': 'Unirme a la Comunidad VIP de WhatsApp',
        'icono_cta': True,
        'marca': 'Conquer Finance',
        'logo': 'img/eventos/cf-logo-horizontal-blanco.png',
        'logo_ancho': 152,
        'gradiente_1': '#aed916',
        'gradiente_2': '#3ac043',
        'titular_1': '#3ac043',
        'titular_2': '#aed916',
    },
    'conquer-languages': {
        'plantilla': 'pages/public/evento/gracias-languages.html',
        'publicada': True,
        'ruta': 'grupos-comunidad',
        'titulo_pagina': 'Gracias-Comunidad',
        'clave': 'gracias-languages',
        'titular': '¡OBLIGATORIO! Queda un último paso para reservar tu entrada...',
        'texto_1': 'Hemos creado una comunidad VIP en WhatsApp para todos los asistentes a la '
                   '<strong>Clase de 0 a Inglés fluido</strong> de Conquer Languages.<br><br>'
                   '<u>Es de vital importancia que te unas para confirmar tu asistencia.</u>',
        'texto_2': '⬇️ Dale al botón verde de abajo para unirte totalmente gratis al grupo '
                   'exclusivo del evento de Conquer Languages ⬇️',
        'destacar_3': '¿Miras más tu Whatsapp que tu e-mail?',
        'texto_3': 'Tranquilo, a mucha gente de nuestra comunidad le ocurre.<br>'
                   'Por eso, hemos creado una comunidad de WhatsApp, donde recibirás todas las '
                   'comunicaciones de la Clase, mucho valor adicional de Conquer Languages, y algún que '
                   'otro regalo.',
        'fondo': 'img/eventos/cl-fondo.jpg',
        'verde': '#15b961',
        'whatsapp': 'https://cl.conquerx.com/5P9e7L/',
        'cta': 'UNIRME A LA COMUNIDAD VIP DE WHATSAPP >>',
        'icono_cta': False,
        'marca': 'Conquer Languages',
        'logo': 'img/eventos/cl-logo-horizontal.png',
        'logo_ancho': 259,
    },
}


# La Trading Week tiene su propia pantalla de gracias, distinta de la que usan
# las pantallas de lanzamiento de Finance: misma maqueta que la de Languages
# —tres tarjetas blancas y el botón verde—, con el fondo azul de Finance y el
# grupo de WhatsApp de esa edición. Cuelga de `/grupos-comunidad`, la URL a la
# que mandaba el original.
GRACIAS_TRADING_WEEK = {
    'plantilla': 'pages/public/evento/gracias-languages.html',
    'plantilla_v2': 'pages/public/evento/gracias-v2.html',
    'ruta': 'grupos-comunidad',
    'titulo_pagina': 'Grupos Comunidad',
    'clave': 'gracias-trading-week',
    'titular': '¡OBLIGATORIO! Queda un último paso para reservar tu entrada...',
    'texto_1': 'Hemos creado una comunidad VIP en WhatsApp para todos los asistentes a la '
               '<strong>Trading Week 2025</strong> de Conquer Finance.<br><br>'
               '<u>Es de vital importancia que te unas para confirmar tu asistencia.</u>',
    'texto_2': '⬇️ Dale al botón verde de abajo para unirte totalmente gratis al grupo '
               'exclusivo del evento de Conquer Finance ⬇️',
    'destacar_3': '¿Miras más tu Whatsapp que tu e-mail?',
    'texto_3': 'Tranquilo, a mucha gente de nuestra comunidad le ocurre.<br>'
               'Por eso, hemos creado una comunidad de WhatsApp, donde recibirás todas las '
               'comunicaciones de la Clase, mucho valor adicional de Conquer Finance, y algún que '
               'otro regalo.',
    'fondo': 'img/eventos/pildoras/fondo-blur.avif',
    'fondo_color': '#000',
    'verde': '#00d663',
    # SIN GRUPO. El del volcado, `chat.wapp.ly/eEZ90a`, ya no lleva a WhatsApp:
    # hoy redirige a winna.com, un casino online. El acortador se reutilizó o
    # cambió de manos desde 2025. Mandar ahí a quien acaba de registrarse en una
    # escuela de finanzas es peor que no mandarlo a ningún sitio, así que se
    # queda vacío: la pantalla se sirve igual, sin botón y sin salto
    # automático, hasta que alguien ponga el enlace bueno.
    'whatsapp': '',
    'cta': 'UNIRME A LA COMUNIDAD VIP DE WHATSAPP >>',
    'icono_cta': False,
    'marca': 'Conquer Finance',
    'logo': 'img/eventos/pildoras/logo.svg',
    'logo_ancho': 200,
}


# Marca de las segundas versiones (?v=2), las que van con el sistema
# "paperboard" de la web actual de cada escuela. Los degradados son los mismos
# que usan sus CTA en las landings de funnel: Blocks dos paradas de ámbar a
# naranja, Finance tres de lima a esmeralda.
#
# Languages no está: su web sigue con el diseño anterior, así que rehacerle las
# páginas de evento la dejaría descolgada de su propio sitio.
MARCAS_V2 = {
    'conquer-blocks': {
        'degradado': 'linear-gradient(90deg,#FFBF00,#FF4000)',
        'acento': '#FF4000',
        'logo': 'img/eventos/v2/logo-cb.png',
        'px_lg': 'img/eventos/v2/px-lg-cb.svg',
        'px_sm': 'img/eventos/v2/px-sm-cb.svg',
    },
    'conquer-finance': {
        'degradado': 'linear-gradient(90deg,#AED916 0%,#74CD2D 50%,#3AC043 100%)',
        'acento': '#74CD2D',
        'logo': 'img/eventos/v2/logo-fi.png',
        'px_lg': 'img/eventos/v2/px-lg-fi.svg',
        'px_sm': 'img/eventos/v2/px-sm-fi.svg',
    },
}


def version(request):
    """Qué versión de la página se pide: 1 (la de siempre) o 2.

    Se elige con `?v=2` y nada más: la vieja sigue siendo la que se sirve por
    defecto, y ninguna se borra. Cuando se decida cuál queda, basta con darle la
    vuelta al valor por defecto aquí.
    """
    return 2 if request.GET.get('v') == '2' else 1


def plantilla_de(ficha, request):
    """Plantilla de la ficha para la versión pedida.

    Solo las páginas que declaran `plantilla_v2` tienen segunda versión; el
    resto ignora el parámetro y sirve la suya.
    """
    if version(request) == 2 and ficha.get('plantilla_v2'):
        return ficha['plantilla_v2']
    return ficha['plantilla']


def _gtm(escuela):
    """Contenedor de GTM de la marca para estas pantallas.

    Las tres lo llevan, incluida Finance. Su página de Webflow no cargaba
    ninguno, así que esto es lo único que se aparta del original a propósito:
    sus lanzamientos estaban sin medir y ahora miden como los demás.
    """
    return get_gtm_config(escuela)


# Páginas de evento de campaña. A diferencia de `EVENTOS` —una por marca, la del
# evento online recurrente— estas son de una campaña concreta, con su propio
# diseño y su propio código de funnel, y conviven varias por marca.
#
# El `funnel` va fijo, no sale de `utm_campaign`: así lo lleva el formulario del
# original.
# Las tres píldoras de la Trading Week, por si otra se enlaza a ellas. Cada
# página enseña tarjetas a las demás, así que la ficha de cada una se declara
# una vez aquí y las otras dos la referencian.
_PILDORAS = {
    1: {'ruta': 'evento/pildoras-evento-1', 'imagen': 'img/eventos/pildoras/pildora-1.avif',
        'clave': 'pildora-1'},
    2: {'ruta': 'evento/pildoras-evento-2', 'imagen': 'img/eventos/pildoras/pildora-2.avif',
        'clave': 'pildora-2'},
    3: {'ruta': 'evento/pildoras-evento-3', 'imagen': 'img/eventos/pildoras/pildora-3.avif',
        'clave': 'pildora-3'},
}


PAGINAS_DE_CAMPANA = {
    'evento-coding-week-eu': {
        'orden': 4,
        'clave': 'coding-week',
        'escuela': 'conquer-blocks',
        'plantilla': 'pages/public/evento/codingweek.html',
        'plantilla_v2': 'pages/public/evento/codingweek-v2.html',
        'titulo_pagina': 'Evento Coding Week - Conquer Blocks EU',
        'funnel': 'cb-codingweek5-eu',
        # Toda la copia de la página. Estaba escrita en las dos plantillas (v1 y
        # v2), que ahora la sacan de aquí: así se edita una sola vez y las dos
        # versiones dicen lo mismo.
        'chapa_evento': 'Evento gratuito y en directo de 2 Días',
        'chapa_fecha': 'El 24 y 25 de Noviembre a las 19:00h Madrid',
        'titular': 'Consigue trabajo 100% remoto y un salario por encima de los '
                   '<strong>3.000€ mensuales</strong> convirtiéndote en Desarrollador Full Stack',
        'subtitular': 'Descubre cómo aprender la habilidad más demandada, en menos de 1 año y '
                      'sin necesidad de experiencia previa',
        'campo_nombre': 'Introduce tu nombre',
        'campo_email': 'Tu mejor email',
        'campo_telefono': 'Número de WhatsApp',
        'legal_pre': 'Al continuar aceptas las',
        'legal_enlace': 'politicas de privacidad',
        'cta': 'Regístrate gratis ahora',
        'reclamo': '¡No lo pienses más y regístrate para acceder a la '
                   '<strong>coding WEEK</strong>!',
        'reclamo_detalle': 'Un evento donde mostraremos el paso a paso para conseguir una '
                           'profesión en auge, con salarios superiores a la media, '
                           '<strong>tasas de desempleo del 0% y 100% remoto.</strong>',
        'tarjetas': (
            {'imagen': 'img/eventos/codingweek/tarjeta-1.avif',
             'titulo': '¿Por qué convertirse en <strong>Desarrollador Full Stack</strong> es la '
                       'mejor opción para asegurar tu futuro?',
             'texto_1': 'En los últimos años, no hemos parado de ver como el precio de todo '
                        'sube, pero como los salarios y las profesiones cada vez son más '
                        'precarias.',
             'texto_2': 'En esta clase entenderás hacia donde se dirige el mercado laboral, y '
                        'cómo tú puedes aprovecharlo para conseguir posicionarte en una '
                        'profesión bien pagada y que te dé la calidad de vida que buscas.'},
            {'imagen': 'img/eventos/codingweek/tarjeta-2.avif',
             'titulo': 'El <strong>Paso a Paso</strong> para conseguirlo en menos de 12 meses y '
                       'disfrutar de <strong>las ventajas de esta habilidad</strong>',
             'texto_1': 'A día de hoy encontrar un empleo, en remoto y con salarios por encima '
                        'a 3.000 euros mensuales, se ha convertido en algo que todo el mundo '
                        'quiere, pero que nadie consigue encontrar.',
             'texto_2': 'En este evento verás como no es tan complicado conseguir todo esto, '
                        'gracias a aprender esta habilidad en menos de 12 meses, '
                        'independientemente de tu experiencia previa o conocimientos.'},
        ),
        # `<strong>` es el resalte de color; `<em>`, el secundario (aquí, la
        # negrita blanca de "coding week").
        'clase0_titulo': 'Conseguirás desbloquear <strong>la clase 0</strong> previa a la '
                         '<em>coding week</em>',
        'clase0_detalle': 'para romper con todos los mitos acerca de las profesiones '
                          'tecnológicas, entender esta profesión, el porqué es tan demandada y '
                          'hasta donde puede llegar a cambiar nuestra vida gracias a ella.',
        'clase0_cartel': 'El sentido común detrás de una de las profesiones más demandadas, con '
                         'mejores condiciones y salarios más altos que la media',
        'bio_titulo': 'Soy <strong>Bienvenido Sáez</strong>',
        'bio_parrafos': [
            'Bienvenido es Director de Educación Tecnológica en Conquer Blocks.',
            'Con más de 20 años de experiencia en el sector del desarrollo y la formación. '
            'Habiendo sido una de las personas más influyentes de este 2025 en el mundo hispano '
            'enseñando una de las profesiones más demandas y mejor pagadas.',
            'En Conquer Blocks enseña un método que ha ayudado a más de 6.000 personas a '
            'aprender una <strong>nueva profesión con la que cambiar sus vidas por '
            'completo</strong>.',
            'Y en este evento te enseñará el porqué deberías aprender una profesión tecnológica, '
            'cómo romper con los mitos acerca de esto, y cómo alcanzar un salario superior a los '
            '3.000 euros mensuales como Desarrollador Full-Stack.',
        ],
        'cierre_antetitulo': '- No la dejes pasar -',
        'cierre_titulo': 'La Coding Week',
        'cierre_texto': 'Prepárate para descubrir cómo <strong>conseguir una profesión con la '
                        'que no sufrir</strong> por la falta de trabajo, los salarios precarios '
                        'o las malas condiciones laborales.',
        'politica_url': 'https://www.conquerblocks.com/politica-de-privacidad',
    },
    'evento-testimonios': {
        'orden': 5,
        'clave': 'testimonios',
        'escuela': 'conquer-blocks',
        'plantilla': 'pages/public/evento/testimonios.html',
        'plantilla_v2': 'pages/public/evento/testimonios-v2.html',
        'titulo_pagina': 'Evento - testimonios',
        # Sin `funnel`: esta no recoge datos. Su único botón lleva a agendar,
        # así que no hay lead, ni pantalla de gracias, ni salto a WhatsApp.
        'funnel': None,
        'cta_texto': 'Agendar mi llamada gratuita',
        'cta_url': ('https://agendar.conquerblocks.com/?utm_source=landing'
                    '&utm_medium=testimonios&utm_campaign=codingweek1'),
        'titular': 'Historias reales de personas que transformaron <strong>su futuro</strong> '
                   'en el sector tech',
        'subtitular': 'Descubre cómo nuestros alumnos consiguieron trabajos bien pagados en '
                      'tiempo récord gracias a nuestra metodología probada',
        'seccion_titulo': 'Conoce la experiencia de nuestros alumnos dentro de Conquer Blocks',
        'sistema_titulo': 'El sistema que garantiza resultados',
        'sistema_puntos': [
            'Método basado en aprender haciendo.',
            'Apoyo de mentores y comunidad activa.',
            'Garantía de empleo al finalizar la formación.',
        ],
        'cierre_titulo': 'Tú podrías ser el <strong>próximo caso de éxito</strong>',
        'cierre_texto': '· Reserva una llamada con nuestro equipo y descubre cómo puedes '
                        'lograrlo ·',
        'video_principal': 'db9ea002-b58a-44ea-8221-31e8d3685c31',
        # Ocho en apaisado y cinco en vertical, en el mismo orden que el
        # original: las dos últimas filas quedan incompletas, no centradas.
        'videos_apaisados': (
            '50a929a1-d5b0-4c98-b918-cc14fc4579e0', '79714730-c00b-47a7-9a20-c3208bb0e243',
            'eb05034a-b9ce-4e12-a08d-ebc3d275cca8', 'f3cbf0aa-d0d4-4eee-a5d7-ecb40e8772ca',
            'af10d2a6-f036-48c0-8ec4-c44e0dcd7318', 'f3d26235-4bdb-4740-9647-9adfc45bc66a',
            'd5f26790-0a3e-4e07-8871-bcf33baa97c9', '6a4875f8-054f-427d-92db-8896363d6e38',
        ),
        'videos_verticales': (
            'a757defb-6c1b-463a-be0b-1cc482fbbe95', '56c0c271-5747-4b8b-8ce6-72a2d9088481',
            'fcd4dbe9-2559-4026-b17d-1d80794305e0', 'a1a2b40d-3fcc-443a-b326-bd180a334286',
            '51b1f995-521e-4f05-97a0-d27d2b65c074',
        ),
        'resenas': tuple(f'img/eventos/testimonios/resena-{n}.avif' for n in range(1, 10)),
        'politica_url': 'https://www.conquerblocks.com/politica-de-privacidad',
    },
    'bitacora': {
        'orden': 6,
        'clave': 'bitacora',
        'escuela': 'conquer-languages',
        'plantilla': 'pages/public/evento/bitacora.html',
        'titulo_pagina': 'bitacora',
        'ruta': 'eventos/bitacora',
        # Tampoco recoge datos: es un vídeo y tres párrafos.
        'funnel': None,
        'biblioteca': '348662',
        'video_principal': '879ce1c6-e0d5-422f-9893-b663a8341f5d',
        'chapa': 'English Week',
        'antetitulo': 'Bienvenidos a La Clase 0',
        # El titular lleva la errata del original ("transforar"). Se replica tal
        # cual; corregirla es ahora un cambio de texto en el admin.
        'titular': 'Prepárate para transforar tu inglés antes de la English Week',
        'parrafos': [
            'Prepárate para la English Week, el evento donde descubrirás por qué cientos de '
            'personas están logrando un inglés fluido en tiempo récord, sin memorizar y sin '
            'horas interminables.',
            'Esta clase previa es clave: te mostrará la mentalidad adecuada, los errores que '
            'frenan tu aprendizaje y el sistema que realmente acelera tu fluidez.',
            'Entenderás por qué sí puedes aprender inglés aunque nada te haya funcionado '
            'antes…<br>y llegarás al evento listo para transformar tu inglés para siempre.',
        ],
        'politica_url': 'https://www.conquerlanguages.com/politica-de-privacidad',
    },
    # Las tres píldoras que precalientan la Trading Week de Finance. No
    # recogen datos: vídeo, texto y enlaces entre ellas. Se recuperaron de
    # web.archive.org —el dominio ya devuelve 404— del último volcado, el de
    # octubre de 2025.
    'pildoras-evento-1': {
        'orden': 7,
        'clave': 'pildora-1',
        'escuela': 'conquer-finance',
        'plantilla': 'pages/public/evento/pildoras.html',
        'plantilla_v2': 'pages/public/evento/pildoras-v2.html',
        'titulo_pagina': 'Pildoras-evento-1',
        'funnel': None,
        'biblioteca': '185796',
        'video_principal': '1806c327-dbfa-4ac4-9c81-bcc8d6240572',
        'numero': 'Píldora Nº1',
        'chapa': 'Trading Week',
        'otras_titulo': 'Sigue con las <strong>demás píldoras</strong>',
        'boton_tarjeta': 'Ya disponible',
        'texto_tarjeta': 'DESCUBRE LA SITUACIÓN ECONÓMICA ACTUAL Y POR QUÉ DEBES ACTUAR YA',
        'titular': 'DESCUBRE LA SITUACIÓN ECONÓMICA ACTUAL Y POR QUÉ DEBES ACTUAR YA',
        'cuerpo': (
            'Prepárate para la <strong>Trading Week</strong>, el evento online en el que '
            'aprenderás cómo generar ingresos con el <strong>Trading</strong>, de manera '
            'rentable y sin riesgos innecesarios.<br><br>'
            'Esta es la primera de 3 píldoras de valor que te ayudarán a entender cómo '
            'aprovechar el evento al máximo. Y no solo eso, sino que entenderás el porqué '
            'debes empezar cuanto antes a aprender esta habilidad este 2025.<br><br>'
            'Ver todas las píldoras es crucial, ya que te permitirán entender las claves '
            'para implementar el <strong>Paso a Paso</strong> que veremos. No te pierdas '
            'ninguna y prepárate para transformar tu situación actual.'
        ),
        # Sin tarjetas: en el original su contenedor llevaba `display: none`, y
        # así estaba desde el primer volcado, así que no es un descuido del
        # último. Se replica.
        'tarjetas': (),
        'politica_url': 'https://www.conquerfinance.com/legal/politica-de-privacidad',
    },
    'pildoras-evento-2': {
        'orden': 8,
        'clave': 'pildora-2',
        'escuela': 'conquer-finance',
        'plantilla': 'pages/public/evento/pildoras.html',
        'plantilla_v2': 'pages/public/evento/pildoras-v2.html',
        'titulo_pagina': 'Pildoras-evento-2',
        'funnel': None,
        'biblioteca': '185796',
        'video_principal': 'd9f08fbc-1782-44e2-bbb8-5194b05db850',
        'numero': 'Píldora Nº2',
        'chapa': 'Trading Week',
        'otras_titulo': 'Sigue con las <strong>demás píldoras</strong>',
        'boton_tarjeta': 'Ya disponible',
        'texto_tarjeta': 'QUÉ ES EL TRADING: LA FORMA MÁS INTELIGENTE DE GENERAR DINERO',
        'titular': 'QUÉ ES EL TRADING: LA FORMA MÁS INTELIGENTE DE GENERAR DINERO',
        'cuerpo': (
            'Esta es la segunda de 3 píldoras de valor que te llevarán a entender el '
            'concepto del Trading Institucional y por qué es mucho más <strong>seguro y '
            'efectivo</strong> que el Trading tradicional, y cómo puedes utilizar el '
            'capital de empresas fondeadoras para <strong>minimizar los riesgos</strong> '
            'y maximizar tus ganancias.<br><br>'
            'Ver todas las píldoras es esencial, ya que te mostrarán paso a paso cómo los '
            'profesionales logran rentabilidades con porcentajes pequeños, pero con '
            'grandes cuentas. No te pierdas ninguna, porque cada una es clave para que '
            'puedas <strong>aprovechar al máximo</strong> LA TRADING WEEK y aprender a '
            'generar entre 2.000 y 5.000 dólares mensuales, gracias a lo que te vamos a '
            'enseñar.'
        ),
        'tarjetas': (_PILDORAS[1], _PILDORAS[3]),
        'politica_url': 'https://www.conquerfinance.com/legal/politica-de-privacidad',
    },
    'pildoras-evento-3': {
        'orden': 9,
        'clave': 'pildora-3',
        'escuela': 'conquer-finance',
        'plantilla': 'pages/public/evento/pildoras.html',
        'plantilla_v2': 'pages/public/evento/pildoras-v2.html',
        'titulo_pagina': 'Pildoras-evento-3',
        'funnel': None,
        'biblioteca': '185796',
        'video_principal': 'b4bb5c13-b44d-4cfe-8c45-efb329b15149',
        'numero': 'Píldora Nº3',
        'chapa': 'Trading Week',
        'otras_titulo': 'Sigue con las <strong>demás píldoras</strong>',
        'boton_tarjeta': 'Ya disponible',
        'texto_tarjeta': 'LOS 3 PERFILES DE PERSONAS QUE TENDRÁN ÉXITO EN EL TRADING '
                         'INSTITUCIONAL',
        'titular': 'LOS 3 PERFILES DE PERSONAS QUE TENDRÁN ÉXITO EN EL TRADING INSTITUCIONAL',
        'cuerpo': (
            'Ahora que ya hemos visto tanto la situación económica actual y el porqué el '
            'trading institucional se está convirtiendo en la manera más inteligente para '
            'generar un ingreso extra mensual este 2025.<br><br>'
            'No importa de dónde vengas o a qué te dediques, hay <strong>tres '
            'perfiles</strong> que están alcanzando el éxito con el <strong>Trading '
            'Institucional</strong>. En esta tercera píldora, te mostramos quiénes son y '
            'cómo saber si eres uno de ellos.<br><br>'
            'Conoce como personas como <strong>José</strong>, <strong>Sara</strong> y '
            '<strong>Miguel</strong> han logrado generar entre <strong>2.000 y 5.000 '
            'dólares mensuales</strong>, con poco riesgo y mayor libertad, siguiendo una '
            'metodología probada.'
        ),
        'tarjetas': (_PILDORAS[1], _PILDORAS[2]),
        'politica_url': 'https://www.conquerfinance.com/legal/politica-de-privacidad',
    },
    # La landing de registro de la Trading Week. Es la única de campaña que
    # recoge datos además de la Coding Week, y la única con test A/B.
    #
    # Del original se dejan fuera dos bloques que ya iban ocultos por CSS: una
    # sección de beneficios con el Lorem Ipsum en inglés de la plantilla de
    # Webflow, y una franja de «Nos has visto en…» con los logos de ejemplo de
    # esa misma plantilla (Twitch, Webflow, Pinterest). Ver la plantilla.
    'trading-week-2025': {
        'orden': 10,
        'clave': 'trading-week',
        'escuela': 'conquer-finance',
        'plantilla': 'pages/public/evento/tradingweek.html',
        'plantilla_v2': 'pages/public/evento/tradingweek-v2.html',
        'titulo_pagina': 'Registro Trading Week 2025',
        # Va en la raíz del dominio, no bajo /evento/.
        'ruta': 'trading-week-2025',
        # Al código se le pega la letra de la variante: `cf-TradingWeek4-a` o
        # `-b`, tal cual lo hacía el script del original.
        'funnel': 'cf-TradingWeek4',
        'gracias': GRACIAS_TRADING_WEEK,
        'variantes': (
            {'codigo': 'a',
             'titular': ('Convierte el trading en tu fuente de ingresos extra, generando de '
                         '<em>2.000 a 5.000 euros mensuales</em> utilizando cuentas fondeadas'),
             'subtitular': ('Aprende el Paso a Paso de la metodología de un fondo de inversión '
                            'probada y con la que cientos de alumnos <em>están obteniendo '
                            'resultados</em>')},
            {'codigo': 'b',
             'titular': ('Descubre el método de trading respaldado por un fondo de inversión de '
                         '$100M en EE.UU y <em>genera resultados</em>'),
             'subtitular': ('Permite a traders sin experiencia <em>generar hasta 5000\u20ac '
                            'mensuales</em> sin arriesgar su capital')},
        ),
        'campo_nombre': 'Introduce tu nombre',
        'campo_email': 'Tu mejor email',
        'legal_pre': 'He leído y acepto la',
        'legal_enlace': 'política de privacidad',
        'aviso': 'Evento gratuito y en directo de 2 Días',
        'fecha': 'Los días 7 y 8 de Abril a las 19:00h de Madrid',
        'cta': 'Regístrate gratis ahora',
        'cta_secundario': 'QUIERO ASISTIR',
        'curso_titulo': '¡Multiplica tus ingresos este 2025 con <strong>trading sin '
                        'arriesgar tu capital</strong>!',
        'curso_bajada': ('Un evento donde mostraremos el paso a paso que ya han implementado más '
                         'de 2.000 alumnos para <strong>empezar a generar ingresos extra</strong>'),
        'columnas': (
            {'imagen': 'img/eventos/tradingweek/curso-1.avif',
             'titulo': '¿Por qué el 2025 Puede Ser tu Mejor Año Financiero?',
             'texto': ('Entenderás qué es el Trading Institucional y el porqué se ha convertido '
                       'en una de las mejores maneras para conseguir un ingreso extra mensual '
                       'este 2025.<br><br>Te enseñaré cómo invierten realmente los profesionales '
                       'y verás como tú también puedes generar un ingreso extra mensual '
                       'utilizando las firmas propietarias, sin necesidad de arriesgar tus '
                       'ahorros y sin tener conocimientos previos sobre el mundo financiero.')},
            {'imagen': 'img/eventos/tradingweek/curso-2.avif',
             'titulo': 'Los Pilares de una Estrategia Rentable en Trading',
             'texto': ('Una vez entendamos qué es el Trading Institucional y la manera en la que '
                       'operan los profesionales, veremos los pilares sobre los que se sustentará '
                       'la metodología que te ayudará a <strong>generar entre 2.000 y 5.000 euros '
                       'mensuales.</strong><br><br>Y las razones por las que algunos Traders no '
                       'son rentables, para no caer en los mismos errores que cometen el 95% de '
                       'las personas que lo intentan.')},
            {'imagen': 'img/eventos/tradingweek/curso-3.avif',
             'titulo': 'El Paso a Paso para generar de 2.000 a 5.000 mensuales con Trading',
             'texto': ('<strong>Descubrirás el Paso a Paso para ser Rentable,</strong> para '
                       'generar un ingreso extra mensual consistente, con una metodología '
                       'probada, y que tan solo tienes que replicar.<br><br>Te mostraré cómo yo y '
                       'mis alumnos lo hacemos, y cómo tú deberías hacerlo si quieres conseguir '
                       'ese ingreso extra en menos de 7 semanas y sin arriesgar tu propio '
                       'capital.')},
        ),
        'taller_titulo': 'Conseguirás <strong>el mini taller previo</strong> a la Trading Week',
        'taller_bajada': ('para que puedas llegar preparado, y entiendas la metodología de '
                          'Trading que te hará generar ese ingreso extra mensual'),
        # Son los titulares de las tres píldoras, que también viven aquí como
        # páginas propias.
        'pildoras': (
            'Descubre la Situación económica Actual y por qué debes actuar YA',
            'Qué es el Trading y por qué se ha convertido en la mejor manera para generar dinero este 2025',
            'Los 3 perfiles de personas que tendrán éxito en el trading (Testimonios y cifras)',
        ),
        'perfil_titulo': 'Soy <strong>Félix Fuertes</strong>',
        'cierre_antetitulo': '- No la dejes pasar -',
        'cierre_titulo': 'La Trading<br>Week',
        'perfil': (
            'Inversor profesional y CEO de Conquer Finance. Después de más de 10 años '
            'dedicándome a los mercados financieros tanto por mi cuenta, como en grandes fondos '
            'de Capital Riesgo. Fundé Conquer Finance, donde enseño una metodología con una '
            'ventaja competitiva, con la que podrás generar un ingreso extra mensual y con la '
            'que he ayudado a más de <strong>2000 personas a vivir del trading sin poner su '
            'capital en riesgo</strong> gracias al método <em>«Trading sin Riesgo»</em>.<br><br>'
            '<em>Metodología que te presentaré en <strong>La Trading week</strong> y que ayuda a '
            'personas a poder vivir mejor, ya sea consiguiendo un extra mensual o dejando su '
            'empleo para dedicar el 100% de su tiempo a operar. Sin tener que buscarse un '
            'segundo empleo y generando entre 2.000 y 5.000 euros mensuales.</em>'
        ),
        'cierre': ('Prepárate para descubrir cómo los traders profesionales generan dinero y '
                   'cómo puedes generar entre <strong>2000 y 5000 euros</strong> gracias a la '
                   'Inversión institucional.'),
        'politica_url': 'https://www.conquerfinance.com/legal/politica-de-privacidad',
    },
}


def _funnel_de_la_edicion(request, evento):
    """Código de la edición con el que se etiqueta el lead en el CRM.

    En Webflow, Blocks y Finance lo copiaban de `utm_campaign` al enviar
    (`getFunnelValue()`), así que la edición viaja en la campaña y nadie toca
    la página al cambiar de lanzamiento; por eso en el CRM conviven
    `cf-lanzamiento10` y `cf-lanzamiento11` sin orden cronológico. Se replica
    igual, con dos salvedades:

    - Solo se acepta la campaña si parece un código de lanzamiento. Cualquier
      otro valor dejaría al lead fuera de `es_lead_de_lanzamiento()` y lo
      mandaría por el pipeline completo del funnel —Supabase, conversiones—,
      que es justo lo que no debe ocurrir.
    - Si no viene campaña se usa el código de `EVENTOS`. Webflow mandaba el
      campo vacío, y un `funnel` vacío tiene ese mismo problema de enrutado.
    """
    campana = (request.GET.get('utm_campaign') or '').strip()
    if 'lanzamiento' in campana.lower():
        # Se recorta al ancho de `Lead.funnel`, que es donde acaba. Sin esto,
        # una campaña larguísima se pintaría entera en la página pero se
        # guardaría cortada, y el código que ve el visitante dejaría de ser el
        # que llega al CRM.
        return campana[:255]
    return evento['funnel']


class EventoView(TemplateView):
    """Pantalla del evento. La escuela se resuelve por dominio, igual que el
    resto de páginas de marca; en local se pasa con ?escuela=."""

    def get(self, request, *args, **kwargs):
        escuela = kwargs.get('escuela') or _escuela_por_host(request)
        self.escuela = escuela
        ficha = EVENTOS.get(escuela)
        if not ficha:
            raise Http404('No hay evento para esta escuela')
        # `con_textos` pone encima lo que se haya editado en el admin; si no hay
        # nada guardado, devuelve la ficha tal cual.
        self.evento = con_textos(ficha, borrador=puede_ver_borrador(request))
        self.template_name = self.evento['plantilla']
        respuesta = super().get(request, *args, **kwargs)
        # Este HTML NO se puede cachear en ningún sitio. Cambia con cada
        # visitante por dos motivos: el código de la edición sale de
        # `utm_campaign`, y el prefijo preseleccionado sale del país del
        # visitante (ver `consentimiento.CABECERA_PAIS`).
        # Una copia cacheada le daría a un visitante la campaña de otro —y sus
        # leads acabarían archivados en la edición equivocada— o el prefijo de
        # otro país. Ya pasó con el HTML del funnel: los navegadores embebidos
        # de TikTok e Instagram cachean con avidez y servían la página vieja.
        respuesta['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        respuesta['Pragma'] = 'no-cache'
        patch_vary_headers(respuesta, (consent.CABECERA_PAIS, 'CF-IPCountry'))
        return respuesta

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['evento'] = self.evento
        ctx['funnel'] = _funnel_de_la_edicion(self.request, self.evento)
        ctx['titulo_pagina'] = self.evento['titulo_pagina']
        # Ruta relativa: vale para cualquier host sin tener que resolver el
        # dominio público de cada marca. Si la escuela ha tenido que venir en la
        # query —el dominio canónico no la resuelve por Host—, se arrastra, o la
        # de gracias no sabría de quién es y respondería 404. En los dominios de
        # marca no hace falta y no se añade.
        # `_base_path` antepone el prefijo bajo el que se esté sirviendo la
        # página (p.ej. /preview). Sin él, registrarse en
        # www.conquerblocks.com/preview/evento/evento-online dejaba en la barra
        # www.conquerblocks.com/evento/gracias-comunidad —la de Webflow—, que es
        # justo de lo que el prefijo sirve para escapar mientras dura la prueba.
        ruta = _base_path(self.request) + '/' + GRACIAS[self.escuela]['ruta']
        if self.request.GET.get('escuela'):
            ruta += '?escuela=' + self.escuela
        ctx['gracias'] = ruta
        # La pantalla de gracias viaja embebida y oculta: al registrarse se
        # muestra sin recargar. Va bajo `gr` porque `EVENTOS` y `GRACIAS`
        # comparten claves con valores distintos (`cta`, `marca`, `logo`…) y
        # volcarlas juntas al contexto se comería la mitad.
        ctx['gr'] = con_textos(GRACIAS[self.escuela],
                               borrador=puede_ver_borrador(self.request))
        ctx['gtm'] = _gtm(self.escuela)
        ctx['consentimiento'] = consent.contexto(self.request, self.escuela)
        # País del selector según Cloudflare. Se manda VACÍO si la cabecera no
        # viene, en vez de caer aquí a 'ES': si el servidor rellena España, el
        # cliente no puede distinguir «Cloudflare dice España» de «Cloudflare no
        # ha dicho nada» y se queda con un prefijo equivocado sin llegar a
        # preguntar. El respaldo por IP y el último recurso de España viven en
        # el JS, que es quien conoce la lista de países.
        ctx['pais_detectado'] = consent.pais(self.request)
        return ctx


class GraciasView(TemplateView):
    """Página de "gracias" del evento, a la que lleva el registro.

    Se resuelve la escuela igual que en `EventoView`. No hace falta prohibir la
    caché como allí: aquí no hay nada que cambie de un visitante a otro."""

    def get(self, request, *args, **kwargs):
        # `/grupos-comunidad` lo comparten dos marcas: en conquerfinance.com es
        # la de la Trading Week y en el resto la de Languages. La ruta lo marca
        # con `compartida`, y entonces solo se decide entre esas dos. Fuera de
        # los dominios de marca —calendar.conquerx.com, que es como se
        # previsualiza— `_escuela_por_host` cae al `?escuela=` de la query, y
        # sin él se queda la de Languages, que es lo que servía esta URL antes
        # de que Finance tuviera la suya.
        if kwargs.pop('compartida', False):
            escuela = _escuela_por_host(request)
            if escuela == 'conquer-finance':
                self.escuela, self.gracias = escuela, con_textos(
                    GRACIAS_TRADING_WEEK, borrador=puede_ver_borrador(request))
            else:
                self.escuela = 'conquer-languages'
                self.gracias = con_textos(GRACIAS['conquer-languages'],
                                          borrador=puede_ver_borrador(request))
            self.template_name = plantilla_de(self.gracias, request)
            return super().get(request, *args, **kwargs)

        escuela = kwargs.get('escuela') or _escuela_por_host(request)
        self.escuela = escuela
        ficha = GRACIAS.get(escuela)
        if not ficha:
            raise Http404('No hay página de gracias para esta escuela')
        self.gracias = con_textos(ficha, borrador=puede_ver_borrador(request))
        self.template_name = plantilla_de(self.gracias, request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['gr'] = self.gracias
        ctx['gtm'] = _gtm(self.escuela)
        ctx['consentimiento'] = consent.contexto(self.request, self.escuela)
        ctx['version'] = version(self.request)
        ctx['marca_v2'] = MARCAS_V2.get(self.escuela)
        return ctx


class PaginaDeCampanaView(TemplateView):
    """Página de evento de una campaña concreta (p.ej. la Coding Week).

    Se resuelve por la ruta, no por el dominio: cada una es de una marca y de
    una campaña, y varias pueden convivir en la misma marca. Por lo demás se
    comporta igual que la pantalla de evento: el registro pasa a la de gracias
    sin recargar y el HTML no se cachea, porque el prefijo depende de quien
    mire."""

    def get(self, request, *args, **kwargs):
        ficha = PAGINAS_DE_CAMPANA.get(kwargs.get('pagina'))
        if not ficha:
            raise Http404('No hay página de campaña con ese nombre')
        self.pagina = con_textos(ficha, borrador=puede_ver_borrador(request))
        self.escuela = self.pagina['escuela']
        self.template_name = plantilla_de(self.pagina, request)
        respuesta = super().get(request, *args, **kwargs)
        respuesta['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        respuesta['Pragma'] = 'no-cache'
        patch_vary_headers(respuesta, (consent.CABECERA_PAIS, 'CF-IPCountry'))
        return respuesta

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pagina'] = self.pagina
        ctx['pais_detectado'] = consent.pais(self.request)
        # Las que no recogen datos —testimonios— no tienen lead que registrar,
        # así que tampoco pantalla de gracias a la que pasar.
        if self.pagina.get('funnel'):
            # La Trading Week tiene pantalla de gracias propia; el resto usa la
            # de su marca.
            gr = con_textos(self.pagina.get('gracias') or GRACIAS[self.escuela],
                            borrador=puede_ver_borrador(self.request))
            ctx['funnel'] = self.pagina['funnel']
            ctx['gracias'] = _base_path(self.request) + '/' + gr['ruta']
            ctx['gr'] = gr
        # Test A/B del titular. En el original lo sorteaba el navegador en cada
        # carga y le pegaba su letra al código de funnel; se hace aquí, en el
        # servidor, para que el titular que se pinta y el código que viaja al
        # CRM sean el mismo por construcción y no dependan de que un script
        # llegue a ejecutarse. La página va con `no-store`, así que no hay
        # caché que fije una variante para todos.
        variantes = self.pagina.get('variantes')
        if variantes:
            variante = random.choice(variantes)
            ctx['variante'] = variante
            if ctx.get('funnel'):
                ctx['funnel'] = f"{ctx['funnel']}-{variante['codigo']}"
        ctx['gtm'] = _gtm(self.escuela)
        ctx['consentimiento'] = consent.contexto(self.request, self.escuela)
        ctx['version'] = version(self.request)
        ctx['marca_v2'] = MARCAS_V2.get(self.escuela)
        return ctx
