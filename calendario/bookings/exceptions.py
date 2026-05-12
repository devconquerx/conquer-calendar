class SlotNoDisponibleError(Exception):
    """El slot pedido no está disponible (ya tomado, fuera de rango, host inactivo, etc.)."""
