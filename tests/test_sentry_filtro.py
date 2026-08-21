"""El filtro de eventos de Sentry en producción."""
from unittest.mock import patch

from django.test import SimpleTestCase


def _cargar_filtro():
    """prod.py no se puede importar en tests (exige variables de entorno), así
    que se lee la función suelta del módulo."""
    import ast
    import textwrap
    fuente = open('config/settings/prod.py').read()
    arbol = ast.parse(fuente)
    fn = next(n for n in arbol.body
              if isinstance(n, ast.FunctionDef) and n.name == '_descartar_ruido')
    espacio = {'sys': __import__('sys')}
    exec(compile(ast.Module([fn], []), '<filtro>', 'exec'), espacio)
    return espacio['_descartar_ruido']


class FiltroSentryTest(SimpleTestCase):

    def setUp(self):
        self.filtro = _cargar_filtro()

    def test_descarta_los_errores_de_manage_py_shell(self):
        with patch('sys.argv', ['manage.py', 'shell']):
            self.assertIsNone(self.filtro({'evento': 1}, {}))

    def test_deja_pasar_los_de_gunicorn(self):
        argv = ['/usr/local/bin/gunicorn', 'config.wsgi:application', '--bind', '0.0.0.0:8000']
        with patch('sys.argv', argv):
            self.assertEqual(self.filtro({'evento': 1}, {}), {'evento': 1})

    def test_deja_pasar_los_de_celery_y_los_comandos_del_cron(self):
        for argv in (['/usr/local/bin/celery', '-A', 'config.celery_app', 'worker'],
                     ['manage.py', 'enviar_recordatorios'],
                     ['manage.py', 'sync_gcal_incremental', '--todos']):
            with patch('sys.argv', argv):
                self.assertIsNotNone(self.filtro({'evento': 1}, {}))

    def test_un_comando_que_solo_se_llame_parecido_no_se_descarta(self):
        with patch('sys.argv', ['manage.py', 'shell_plus_algo']):
            self.assertIsNotNone(self.filtro({'evento': 1}, {}))
