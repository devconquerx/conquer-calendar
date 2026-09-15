class SlotNoDisponibleError(Exception):
    """El slot pedido no está disponible (ya tomado, fuera de rango, host inactivo, etc.)."""


class ReservaDuplicadaError(Exception):
    """El invitado ya tiene una reserva futura confirmada para este event_type
    (y el event_type tiene unico_por_invitado=True).
    Lleva la reserva existente como payload para que la vista pueda ofrecer
    cancelar la vieja y crear la nueva."""

    def __init__(self, reserva_existente):
        self.reserva_existente = reserva_existente
        super().__init__("Ya existe una reserva futura para este invitado.")


class InvitadoBloqueadoError(Exception):
    """El email del invitado (o su dominio) está bloqueado en el admin.
    Lleva el `BloqueoInvitado` que lo frenó para que la vista cuente el intento
    y redirija a la URL configurada."""

    def __init__(self, bloqueo, email=''):
        self.bloqueo = bloqueo
        self.email = email
        super().__init__("El invitado no puede reservar.")


class LimiteReservasError(Exception):
    """El invitado ya tiene el máximo de reservas que admite el tipo de evento
    en su ventana de días (`limite_reservas` cada `limite_reservas_dias`).
    `disponible_desde` es el primer día en que podría volver a reservar, o None
    si no se encontró."""

    def __init__(self, event_type, disponible_desde=None):
        self.event_type = event_type
        self.disponible_desde = disponible_desde
        super().__init__("El invitado alcanzó el máximo de reservas de este evento.")
