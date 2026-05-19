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
