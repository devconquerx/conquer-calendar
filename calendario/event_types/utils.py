from django.db.models import Q

from .models import EventType


def event_types_visibles(user):
    """Tipos de evento que `user` puede ver y gestionar.

    - admin      → todos
    - resto      → los suyos, en los que participa, y los de los miembros de
                   los grupos que supervisa

    Devuelve un queryset sin `distinct()` para poder seguir componiendo filtros.
    """
    if user.es_admin:
        return EventType.objects.all()

    from calendario.grupos.utils import miembros_de_mis_grupos

    q = Q(host=user) | Q(hosts_pool__host=user)
    grupo_ids = miembros_de_mis_grupos(user)
    if grupo_ids:
        q |= Q(host_id__in=grupo_ids)
    return EventType.objects.filter(q)
