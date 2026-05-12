from .bootstrap import KTBootstrap
from .libs.theme import KTTheme


class KTLayout:
    """Inicializa tema/layout en el contexto. CONFIGURATION se inyecta vía
    context_processor (calendario.users.context_processors.calendario_context),
    por eso aquí no se importa ningún modelo del CRM."""

    @staticmethod
    def init(context):
        KTTheme.init()
        context.update({
            'layout': KTTheme.setLayout('default.html', context),
        })
        KTBootstrap.init()
        return context
