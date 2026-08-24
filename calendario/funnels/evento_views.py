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
from django.conf import settings
from django.http import Http404
from django.utils.cache import patch_vary_headers
from django.views.generic import TemplateView

from .context_processors import get_gtm_config
from .views import _escuela_por_host


# Contenido por escuela. Lo que cambia entre ediciones es `barra` (fecha y hora)
# y, si acaso, el titular; el resto se mantiene.
EVENTOS = {
    'conquer-blocks': {
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
    },
    'conquer-finance': {
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
    },
    'conquer-languages': {
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
        'ruta': 'evento/gracias-comunidad',
        'titulo_pagina': 'Gracias Comunidad',
        'whatsapp': 'https://cb.conquerx.com/1Qt1ef/',
        'clase': 'Clase Privada de Conquer Blocks.',
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
        'ruta': 'evento/gracias-comunidad',
        'titulo_pagina': '¡Registro Confirmado! - Trading Week | Conquer Finance',
        # OJO: es el grupo de Blocks, tal como está hoy en Webflow.
        'whatsapp': 'https://cb.conquerx.com/1Qt1ef/',
        'clase': 'Clase Privada de Conquer Finance.',
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
        'ruta': 'grupos-comunidad',
        'titulo_pagina': 'Gracias-Comunidad',
        'whatsapp': 'https://cl.conquerx.com/5P9e7L/',
        'clase': 'Clase de 0 a Inglés fluido',
        'cta': 'UNIRME A LA COMUNIDAD VIP DE WHATSAPP >>',
        'icono_cta': False,
        'marca': 'Conquer Languages',
        'logo': 'img/eventos/cl-logo-horizontal.png',
        'logo_ancho': 259,
    },
}


def _gtm(escuela):
    """Contenedor de GTM de la marca para estas pantallas.

    Las tres lo llevan, incluida Finance. Su página de Webflow no cargaba
    ninguno, así que esto es lo único que se aparta del original a propósito:
    sus lanzamientos estaban sin medir y ahora miden como los demás.
    """
    return get_gtm_config(escuela)


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
        self.evento = EVENTOS.get(escuela)
        if not self.evento:
            raise Http404('No hay evento para esta escuela')
        self.template_name = self.evento['plantilla']
        respuesta = super().get(request, *args, **kwargs)
        # Este HTML NO se puede cachear en ningún sitio. Cambia con cada
        # visitante por dos motivos: el código de la edición sale de
        # `utm_campaign`, y el prefijo preseleccionado sale de `CF-IPCountry`.
        # Una copia cacheada le daría a un visitante la campaña de otro —y sus
        # leads acabarían archivados en la edición equivocada— o el prefijo de
        # otro país. Ya pasó con el HTML del funnel: los navegadores embebidos
        # de TikTok e Instagram cachean con avidez y servían la página vieja.
        respuesta['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        respuesta['Pragma'] = 'no-cache'
        patch_vary_headers(respuesta, ('CF-IPCountry',))
        return respuesta

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['evento'] = self.evento
        ctx['funnel'] = _funnel_de_la_edicion(self.request, self.evento)
        ctx['titulo_pagina'] = self.evento['titulo_pagina']
        ctx['gracias'] = '/' + GRACIAS[self.escuela]['ruta']
        ctx['gtm'] = _gtm(self.escuela)
        # País del selector según Cloudflare. Se manda VACÍO si la cabecera no
        # viene, en vez de caer aquí a 'ES': si el servidor rellena España, el
        # cliente no puede distinguir «Cloudflare dice España» de «Cloudflare no
        # ha dicho nada» y se queda con un prefijo equivocado sin llegar a
        # preguntar. El respaldo por IP y el último recurso de España viven en
        # el JS, que es quien conoce la lista de países.
        ctx['pais_detectado'] = (self.request.headers.get('CF-IPCountry') or '').upper()
        return ctx


class GraciasView(TemplateView):
    """Página de "gracias" del evento, a la que lleva el registro.

    Se resuelve la escuela igual que en `EventoView`. No hace falta prohibir la
    caché como allí: aquí no hay nada que cambie de un visitante a otro."""

    def get(self, request, *args, **kwargs):
        escuela = kwargs.get('escuela') or _escuela_por_host(request)
        self.escuela = escuela
        self.gracias = GRACIAS.get(escuela)
        if not self.gracias:
            raise Http404('No hay página de gracias para esta escuela')
        self.template_name = self.gracias['plantilla']
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.gracias)
        ctx['gtm'] = _gtm(self.escuela)
        return ctx
