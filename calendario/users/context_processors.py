from metronic.libs.theme import KTTheme


def calendario_context(request):
    # Reset Metronic per-request state (KTTheme usa variables de clase)
    KTTheme.htmlAttributes = {}
    KTTheme.htmlClasses = {}
    KTTheme.vendorFiles = []
    KTTheme.javascriptFiles = []
    KTTheme.cssFiles = []

    permisos = set()
    if request.user.is_authenticated:
        permisos = request.user.permisos_codenames

    return {
        'CONFIGURATION': {'app_name': 'Conquer Calendario'},
        'PERMISOS_USUARIO': permisos,
    }
