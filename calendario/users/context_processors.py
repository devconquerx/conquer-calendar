from metronic.libs.theme import KTTheme


def calendario_context(request):
    # Reset Metronic per-request state (KTTheme usa variables de clase)
    KTTheme.htmlAttributes = {}
    KTTheme.htmlClasses = {}
    KTTheme.vendorFiles = []
    KTTheme.javascriptFiles = []
    KTTheme.cssFiles = []

    permisos = set()
    magic_login_admin = None

    if request.user.is_authenticated:
        permisos = request.user.permisos_codenames
        admin_pk = request.session.get('magic_login_admin_pk')
        if admin_pk:
            try:
                from calendario.users.models import User
                magic_login_admin = User.objects.get(pk=admin_pk)
            except User.DoesNotExist:
                pass

    return {
        'CONFIGURATION': {'app_name': 'Conquer Calendario'},
        'PERMISOS_USUARIO': permisos,
        'magic_login_admin': magic_login_admin,
    }
