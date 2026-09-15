"""Bloqueo de invitados por email o por dominio.

Los bloqueos se dan de alta en el admin (`BloqueoInvitado`) y se comprueban en
`crear_reserva` y `reemplazar_reserva`, que son la única puerta por la que
entran las reservas públicas: página del host, equipo, enlace único, modal de
duplicado y funnel. Quien está bloqueado no ve un error: se le redirige a la URL
de `ConfigBloqueos`, sin explicarle el motivo para no darle pistas de cómo
saltárselo.
"""

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


def buscar_bloqueo(email):
    """Devuelve el `BloqueoInvitado` activo que afecta a este email, o None."""
    from .models import BloqueoInvitado

    email = (email or '').strip().lower()
    if '@' not in email:
        return None
    dominio = email.rpartition('@')[2]
    buzon = _buzon(email)

    for bloqueo in BloqueoInvitado.objects.filter(activo=True).order_by('pk'):
        if bloqueo.tipo == BloqueoInvitado.Tipo.EMAIL:
            if '@' in bloqueo.valor and _buzon(bloqueo.valor) == buzon:
                return bloqueo
        elif bloqueo.valor and _dominio_coincide(dominio, bloqueo.valor):
            return bloqueo
    return None
