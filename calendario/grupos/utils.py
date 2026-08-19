def miembros_de_mis_grupos(user):
    """PKs de todos los usuarios en grupos donde `user` es supervisor (excluye al propio user)."""
    from .models import GrupoXUsuario
    grupo_ids = GrupoXUsuario.objects.filter(
        usuario=user,
        es_supervisor=True,
    ).values_list('grupo_id', flat=True)
    return list(
        GrupoXUsuario.objects.filter(grupo_id__in=grupo_ids)
        .exclude(usuario=user)
        .values_list('usuario_id', flat=True)
        .distinct()
    )


def usuario_bloqueado(user, campo, request=None):
    """
    True si el usuario es miembro (no supervisor) de algún grupo con el flag activado.
    - Los supervisores nunca quedan bloqueados.
    - En modo magic login (supervisor actuando como host) el bloqueo se salta.
    """
    if request and request.session.get('magic_login_admin_pk'):
        return False
    from .models import GrupoXUsuario
    return GrupoXUsuario.objects.filter(
        usuario=user,
        es_supervisor=False,
        **{f'grupo__{campo}': True},
    ).exists()


def hosts_editables(user):
    """
    Usuarios cuya disponibilidad/zona horaria puede gestionar `user` desde el
    panel de disponibilidad, sin necesidad de suplantarlo (magic login):

    - admin        → todos los usuarios activos
    - supervisor   → él mismo + los miembros de los grupos que supervisa
    - resto        → solo él mismo

    Devuelve siempre un queryset de User ordenado por nombre.
    """
    from django.db.models import Q
    from calendario.users.models import User
    from .models import GrupoXUsuario

    if user.es_admin:
        return User.objects.filter(is_active=True).order_by(
            'first_name', 'last_name', 'email'
        )

    grupo_ids = list(
        GrupoXUsuario.objects.filter(usuario=user, es_supervisor=True)
        .values_list('grupo_id', flat=True)
    )
    if not grupo_ids:
        return User.objects.filter(pk=user.pk)

    return User.objects.filter(
        Q(pk=user.pk)
        | Q(is_active=True, membresias_grupo__grupo_id__in=grupo_ids)
    ).distinct().order_by('first_name', 'last_name', 'email')


def puede_editar_host(user, host):
    """True si `user` puede gestionar la disponibilidad de `host`."""
    if user.pk == host.pk:
        return True
    return hosts_editables(user).filter(pk=host.pk).exists()
