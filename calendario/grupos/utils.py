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
