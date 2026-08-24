"""
Reserva embebida en el LMS de la academia.

Los tipos de evento marcados como «solo alumnos» (``EventType.acceso``) no se
pueden reservar por su enlace público: hay que llegar con un token que el LMS
firma con un secreto compartido. Aquí solo se verifica esa firma.

Lo que NO hace este módulo, a propósito:

  * no guarda ni consulta ninguna lista de alumnos —esta app no sabe quién está
    matriculado y no tiene por qué saberlo—;
  * no llama al LMS para preguntar nada, así que una caída del LMS no impide
    reservar a quien ya tiene su token;
  * no decide quién puede reservar. Eso lo decide el LMS al emitir el token.

De ahí que no haga falta sincronizar usuarios entre las dos apps: cuando a un
alumno se le retira el acceso, el LMS deja de emitirle token y esto se corta
solo, sin que nadie tenga que tocar nada de este lado.

El token viaja en la URL del iframe (``?t=...``) y de ahí se cuelga también del
`action` del formulario y de la URL de slots, para que sobreviva al envío. Es
legible —va firmado, no cifrado—, así que dentro va lo mínimo para crear la
reserva y nada más.
"""
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.shortcuts import render


PARAM = 't'

# Lo que se espera dentro del token. `telefono` es opcional y solo sirve para
# prellenar: el alumno puede corregirlo. `nombre` y `email` no, porque son la
# identidad que el LMS está respaldando con su firma.
CAMPOS_OBLIGATORIOS = ('email', 'nombre')


class AccesoDenegado(Exception):
    """No hay token válido para un evento que lo exige.

    Lleva un texto pensado para enseñárselo a la persona, no un código: buena
    parte de quien va a ver esta pantalla no tiene ni idea de qué es un token,
    y un 403 pelado acaba en una llamada a soporte.
    """

    def __init__(self, motivo, titulo, detalle):
        super().__init__(f'{motivo}: {titulo}')
        self.motivo = motivo
        self.titulo = titulo
        self.detalle = detalle


def _config_incompleta():
    return not settings.EMBED_LMS_SECRET


def firmar_token(payload):
    """Firma un payload igual que lo haría el LMS.

    Existe para los tests y para poder generar un token de ejemplo con el que
    comprobar contra el LMS que las dos partes se entienden. En producción quien
    firma es siempre el LMS; esta app solo verifica.
    """
    return signing.dumps(
        payload,
        key=settings.EMBED_LMS_SECRET,
        salt=settings.EMBED_LMS_SALT,
    )


def leer_token(raw):
    """Devuelve el payload del token o levanta AccesoDenegado."""
    if not raw:
        raise AccesoDenegado(
            'ausente',
            'Esta página se abre desde la academia',
            'Entra a la academia y reserva desde ahí. Este enlace por sí solo '
            'no funciona.',
        )

    if _config_incompleta():
        # Desplegado sin el secreto. Se cierra en vez de abrirse: un fallo de
        # configuración no puede acabar dejando entrar a cualquiera.
        raise AccesoDenegado(
            'sin_configurar',
            'Las reservas para alumnos no están disponibles',
            'Vuelve a intentarlo en un rato. Si sigue igual, avisa a soporte.',
        )

    try:
        datos = signing.loads(
            raw,
            key=settings.EMBED_LMS_SECRET,
            salt=settings.EMBED_LMS_SALT,
            max_age=settings.EMBED_LMS_MAX_AGE,
        )
    except signing.SignatureExpired:
        raise AccesoDenegado(
            'caducado',
            'Esta página llevaba demasiado tiempo abierta',
            'Por seguridad ha caducado. Vuelve a entrar desde la academia y '
            'podrás reservar con normalidad.',
        )
    except signing.BadSignature:
        raise AccesoDenegado(
            'invalido',
            'Este enlace no es válido',
            'Entra a la academia y reserva desde ahí.',
        )

    if not isinstance(datos, dict) or any(not datos.get(c) for c in CAMPOS_OBLIGATORIOS):
        # Firma buena pero contenido que no sirve para crear la reserva. Es un
        # fallo del LMS, no de quien está delante, así que no se le echa la
        # culpa en el texto.
        raise AccesoDenegado(
            'incompleto',
            'Faltan datos para reservar',
            'Vuelve a entrar desde la academia. Si sigue igual, avisa a soporte.',
        )

    return {
        'uid': datos.get('uid', ''),
        'email': datos['email'].strip(),
        'nombre': datos['nombre'].strip(),
        'telefono': (datos.get('telefono') or '').strip(),
    }


def token_de_request(request):
    """El token tal cual viene en el querystring.

    Va en la URL —tanto en la del iframe como en el `action` del formulario— y
    no en un campo oculto, para que comprobarlo no obligue a leer el cuerpo de
    la petición: el middleware que exime del CSRF corre antes que la vista y
    tocar `request.POST` ahí le rompería el `request.body` a otras vistas.
    """
    return (request.GET.get(PARAM) or '').strip()


def con_token(url, token):
    """Cuelga el token de una URL de la propia app (el `action`, el de slots)."""
    if not token:
        return url
    return f'{url}{"&" if "?" in url else "?"}{PARAM}={quote(token)}'


def invitado_de_request(request, event_type):
    """Payload del alumno, o None si el evento no exige token.

    Levanta AccesoDenegado si lo exige y no hay uno bueno.
    """
    if not event_type.solo_alumnos:
        return None
    return leer_token(token_de_request(request))


def aplicar_embed(ctx, invitado, token):
    """Adapta el contexto de la página de reserva al modo embebido.

    Con `invitado` a None (evento público) no toca nada, así que el formulario
    de siempre se comporta exactamente igual que antes de existir esto.
    """
    if invitado is None:
        return ctx

    ctx.update({
        'embed': True,
        'embed_token': token,
        # Bloqueados: son la identidad que el LMS firma. Aunque alguien
        # comparta el enlace, la reserva queda a nombre de este alumno y el
        # correo de confirmación le llega a él.
        'nombre_invitado': invitado['nombre'],
        'email_invitado': invitado['email'],
        'campos_identidad_bloqueados': True,
    })
    # Prellenado pero editable: si el LMS lo tiene desactualizado, que la
    # persona lo pueda corregir. Falsearlo no le da acceso a nada. Solo se pisa
    # si viene algo, para no borrar lo que la persona ya hubiera escrito cuando
    # el formulario se repinta con errores.
    if invitado['telefono'] and not ctx.get('telefono_invitado'):
        ctx['telefono_invitado'] = invitado['telefono']

    # El token tiene que sobrevivir al envío del formulario y a la carga de
    # slots por AJAX, o la reserva se caería en el POST.
    for clave in ('form_action_url', 'slots_url'):
        if ctx.get(clave):
            ctx[clave] = con_token(ctx[clave], token)
    return ctx


def respuesta_denegada(request, exc):
    """Página de acceso denegado, pintable dentro del iframe.

    Se le deja embeber a propósito: si se bloqueara, la persona vería un hueco
    en blanco dentro de la academia y no habría forma de contarle qué pasa ni de
    ofrecerle recargar.
    """
    resp = render(
        request,
        'pages/public/booking/acceso_denegado.html',
        {'titulo': exc.titulo, 'detalle': exc.detalle, 'motivo': exc.motivo},
        status=403,
    )
    return permitir_embebido(resp)


def permitir_embebido(response):
    """Deja que la respuesta se pueda pintar dentro del iframe del LMS.

    Sin esto, XFrameOptionsMiddleware manda `X-Frame-Options: DENY` y el iframe
    sale en blanco por muy bueno que sea el token. `frame-ancestors` es la
    versión moderna y la única que admite una lista de orígenes.
    """
    origenes = getattr(settings, 'EMBED_LMS_ORIGENES', None)
    if not origenes:
        return response
    response['Content-Security-Policy'] = 'frame-ancestors ' + ' '.join(origenes)
    response.xframe_options_exempt = True
    return response
