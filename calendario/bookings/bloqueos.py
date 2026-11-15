"""Bloqueo de invitados por email, por dominio o por teléfono.

Los bloqueos se dan de alta en el admin (`BloqueoInvitado`) y se comprueban en
`crear_reserva` y `reemplazar_reserva`, que son la única puerta por la que
entran las reservas públicas: página del host, equipo, enlace único, modal de
duplicado y funnel. Quien está bloqueado no ve un error: se le redirige a la URL
de `ConfigBloqueos`, sin explicarle el motivo para no darle pistas de cómo
saltárselo.

El teléfono va en el mismo bloqueo, como campo opcional: quien está bloqueado
lo primero que hace es reservar con otro correo, pero casi nunca cambia de
número. Un bloqueo frena la reserva si coincide el email (o el dominio) O el
teléfono.
"""
import logging
import re

from django.db.models import F
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

try:
    import phonenumbers
except ImportError:  # pragma: no cover
    phonenumbers = None

logger = logging.getLogger(__name__)

# Proveedores que ignoran los puntos de la parte local: pepito@gmail.com y
# pe.pi.to@gmail.com son el mismo buzón.
_DOMINIOS_SIN_PUNTOS = {'gmail.com', 'googlemail.com'}


def normalizar_valor(tipo, valor):
    """Forma en la que se guarda un bloqueo: minúsculas, sin espacios y, en los
    dominios, sin la arroba del principio (se suele escribir «@somoshackers»)."""
    from .models import BloqueoInvitado

    valor = (valor or '').strip().lower()
    if tipo == BloqueoInvitado.Tipo.DOMINIO:
        valor = valor.lstrip('@').strip('.')
    return valor


def normalizar_telefono(valor):
    """Teléfono en E.164 sin espacios («+5353595535»), o '' si no es un número
    reconocible.

    Es la forma en la que se guarda el bloqueo y con la que se compara el
    teléfono de la reserva, así da igual cómo se haya escrito cada uno
    («+53 5359 5535», «+53-53595535»…). Hace falta el prefijo del país: sin él
    no hay forma de saber de dónde es el número.
    """
    limpio = re.sub(r'[^\d+]', '', valor or '')
    if limpio.startswith('00'):
        limpio = '+' + limpio[2:]
    if not limpio.startswith('+') or len(limpio) < 6:
        return ''
    # Móviles mexicanos con el "1" de antes de 2019 (lo arrastra WhatsApp): son
    # el mismo número que sin él. Misma regla que `normalizarTelefono` del front.
    mexicano = re.match(r'^\+52(?:1|045|01)(\d{10})$', limpio)
    if mexicano:
        limpio = '+52' + mexicano.group(1)
    if phonenumbers is None:
        return limpio
    try:
        numero = phonenumbers.parse(limpio, None)
    except phonenumbers.NumberParseException:
        return ''
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


def _buzon(email):
    """Email reducido al buzón que de verdad recibe el correo.

    Sin esto el bloqueo de un email concreto se salta con un «+loquesea»
    (pepito+1@gmail.com llega a pepito@gmail.com en casi todos los
    proveedores) o, en Gmail, poniendo puntos en medio.
    """
    local, _, dominio = email.strip().lower().rpartition('@')
    local = local.split('+', 1)[0]
    if dominio in _DOMINIOS_SIN_PUNTOS:
        local = local.replace('.', '')
    return f'{local}@{dominio}'


def _dominio_coincide(dominio_email, bloqueado):
    """¿El dominio del email cae dentro del dominio bloqueado?

    - Con extensión («somoshackers.com»): ese dominio y sus subdominios
      («mail.somoshackers.com»), pero no «nosomoshackers.com».
    - Sin extensión («somoshackers»): cualquier terminación
      («somoshackers.net», «somoshackers.co.uk», «mail.somoshackers.es»). Se
      mira cada parte del dominio menos la última, para que bloquear «com» no
      se lleve por delante a todo el mundo.
    """
    if '.' in bloqueado:
        return dominio_email == bloqueado or dominio_email.endswith('.' + bloqueado)
    return bloqueado in dominio_email.split('.')[:-1]


def buscar_bloqueo(email, telefono=''):
    """Devuelve el `BloqueoInvitado` activo que afecta a este email o a este
    teléfono, o None."""
    from .models import BloqueoInvitado

    email = (email or '').strip().lower()
    tiene_email = '@' in email
    dominio = email.rpartition('@')[2] if tiene_email else ''
    buzon = _buzon(email) if tiene_email else ''
    telefono = normalizar_telefono(telefono)
    if not tiene_email and not telefono:
        return None

    for bloqueo in BloqueoInvitado.objects.filter(activo=True).order_by('pk'):
        if telefono and bloqueo.telefono and bloqueo.telefono == telefono:
            return bloqueo
        if not tiene_email or not bloqueo.valor:
            continue
        if bloqueo.tipo == BloqueoInvitado.Tipo.EMAIL:
            if '@' in bloqueo.valor and _buzon(bloqueo.valor) == buzon:
                return bloqueo
        elif _dominio_coincide(dominio, bloqueo.valor):
            return bloqueo
    return None


def registrar_intento(bloqueo, email='', telefono=''):
    """Suma el intento al contador del bloqueo.

    Va aparte de `crear_reserva` a propósito: la excepción deshace la
    transacción en la que se lanza, y con ella se perdería este UPDATE.
    """
    from .models import BloqueoInvitado

    BloqueoInvitado.objects.filter(pk=bloqueo.pk).update(
        intentos=F('intentos') + 1, ultimo_intento=timezone.now(),
    )
    logger.warning(
        'Reserva frenada por bloqueo %s (%s): email=%s telefono=%s',
        bloqueo.pk, bloqueo, email, telefono,
    )


def url_bloqueo(request):
    """URL absoluta a la que se manda a quien está bloqueado.

    Absoluta porque el funnel puede estar servido desde el dominio de la
    escuela, y una ruta relativa acabaría en ese dominio y no en el nuestro.
    """
    from .models import ConfigBloqueos

    url = ConfigBloqueos.get().url_redireccion
    if url:
        return url
    return request.build_absolute_uri(reverse('public_token:reserva_no_procesada'))


def redirigir(request, error):
    """Respuesta de las vistas HTML cuando `crear_reserva` lanza el bloqueo."""
    registrar_intento(error.bloqueo, error.email, error.telefono)
    return redirect(url_bloqueo(request))
