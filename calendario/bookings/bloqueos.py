"""Bloqueo de invitados por email o por dominio.

Los bloqueos se dan de alta en el admin (`BloqueoInvitado`) y se comprueban en
`crear_reserva` y `reemplazar_reserva`, que son la única puerta por la que
entran las reservas públicas: página del host, equipo, enlace único, modal de
duplicado y funnel. Quien está bloqueado no ve un error: se le redirige a la URL
de `ConfigBloqueos`, sin explicarle el motivo para no darle pistas de cómo
saltárselo.
"""


def normalizar_valor(tipo, valor):
    """Forma en la que se guarda un bloqueo: minúsculas, sin espacios y, en los
    dominios, sin la arroba del principio (se suele escribir «@somoshackers»)."""
    from .models import BloqueoInvitado

    valor = (valor or '').strip().lower()
    if tipo == BloqueoInvitado.Tipo.DOMINIO:
        valor = valor.lstrip('@').strip('.')
    return valor
