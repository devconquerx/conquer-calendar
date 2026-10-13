"""
El cron sincroniza cada host cada 10 minutos: un fallo de Google no puede
convertirse en un aviso por pasada.

- FUNNELS-2E: `unauthorized_client` suelto con un host que va bien; la pasada
  siguiente funciona. No es para avisar.
- FUNNELS-1F: un host sin Google Calendar (`notACalendarUser`) fallaba en cada
  pasada y cada una era un error en Sentry.
"""
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from google.auth.exceptions import RefreshError

from calendario.google_calendar.models import GoogleCalendarSyncEstado
from calendario.google_calendar.sync import sincronizar_host_incremental
from tests.factories import crear_host

PATCH_SERVICIO = 'calendario.google_calendar.sync.obtener_servicio_calendar'
LOGGER = 'calendario.google_calendar.sync'


def _servicio(execute):
    servicio = MagicMock()
    servicio.events.return_value.list.return_value.execute.side_effect = execute
    servicio.events.return_value.list_next.return_value = None
    return servicio


def _falla():
    raise RefreshError('unauthorized_client')


def _va_bien():
    return {'items': [], 'nextSyncToken': 'token-nuevo'}


class AvisosDeFalloTest(TestCase):

    def setUp(self):
        cache.clear()
        self.host = crear_host()
        GoogleCalendarSyncEstado.objects.update_or_create(
            host=self.host, defaults={'sync_token': 'token-viejo',
                                      'estado': GoogleCalendarSyncEstado.ACTIVO})

    def _pasada(self, execute):
        with patch(PATCH_SERVICIO, return_value=_servicio(execute)):
            with self.assertLogs(LOGGER, level='INFO') as logs:
                sincronizar_host_incremental(self.host)
        return [r.levelname for r in logs.records if 'sync_incremental' in r.getMessage()
                and 'OK' not in r.getMessage()]

    def _estado(self):
        return GoogleCalendarSyncEstado.objects.get(host=self.host).estado

    def test_un_fallo_suelto_es_warning(self):
        self.assertEqual(self._pasada(_falla), ['WARNING'])
        self.assertEqual(self._estado(), GoogleCalendarSyncEstado.ERROR)

    def test_si_se_repite_avisa_una_sola_vez(self):
        niveles = [self._pasada(_falla) for _ in range(4)]
        self.assertEqual(niveles, [['WARNING'], ['ERROR'], ['WARNING'], ['WARNING']])

    def test_al_recuperarse_vuelve_a_avisar_si_se_rompe_otra_vez(self):
        self._pasada(_falla)
        self._pasada(_falla)
        self._pasada(_va_bien)
        self.assertEqual(self._estado(), GoogleCalendarSyncEstado.ACTIVO)
        self.assertEqual([self._pasada(_falla), self._pasada(_falla)], [['WARNING'], ['ERROR']])
