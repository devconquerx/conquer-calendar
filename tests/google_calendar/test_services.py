from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase

from calendario.bookings.models import Reserva
from calendario.google_calendar.services import consultar_freebusy
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)


def _reserva_en_bd(host, et, inicio=None):
    """Crea una reserva directamente en BD sin pasar por el servicio (sin mocks)."""
    inicio = inicio or slot_futuro()
    return Reserva.objects.create(
        event_type=et,
        host=host,
        inicio_utc=inicio,
        fin_utc=inicio + timedelta(minutes=et.duracion_minutos),
        nombre_invitado='Santiago Centeno',
        email_invitado='santiagocentenot@gmail.com',
        estado=Reserva.Estado.CONFIRMADA,
    )


class FreeBusyTest(TestCase):

    def setUp(self):
        self.host = crear_host()

    @patch('calendario.google_calendar.services.build')
    @patch('calendario.google_calendar.services.service_account')
    def test_freebusy_ocupado_devuelve_true(self, mock_sa, mock_build):
        servicio = MagicMock()
        mock_build.return_value = servicio
        mock_sa.Credentials.from_service_account_file.return_value.with_subject.return_value = MagicMock()

        servicio.calendarList().list().execute.return_value = {
            'items': [{'id': 'primary', 'primary': True}]
        }
        servicio.freebusy().query().execute.return_value = {
            'calendars': {'primary': {'busy': [{'start': 'x', 'end': 'y'}]}}
        }

        inicio = slot_futuro()
        resultado = consultar_freebusy(self.host.email, inicio, inicio + timedelta(minutes=30))
        self.assertTrue(resultado)

    @patch('calendario.google_calendar.services.build')
    @patch('calendario.google_calendar.services.service_account')
    def test_freebusy_libre_devuelve_false(self, mock_sa, mock_build):
        servicio = MagicMock()
        mock_build.return_value = servicio
        mock_sa.Credentials.from_service_account_file.return_value.with_subject.return_value = MagicMock()

        servicio.calendarList().list().execute.return_value = {
            'items': [{'id': 'primary', 'primary': True}]
        }
        servicio.freebusy().query().execute.return_value = {
            'calendars': {'primary': {'busy': []}}
        }

        inicio = slot_futuro()
        resultado = consultar_freebusy(self.host.email, inicio, inicio + timedelta(minutes=30))
        self.assertFalse(resultado)

    @patch('calendario.google_calendar.services.build')
    @patch('calendario.google_calendar.services.service_account')
    def test_freebusy_error_google_fail_open(self, mock_sa, mock_build):
        """Si Google falla en la query, devuelve False (no bloquea la reserva)."""
        servicio = MagicMock()
        mock_build.return_value = servicio
        mock_sa.Credentials.from_service_account_file.return_value.with_subject.return_value = MagicMock()

        servicio.calendarList().list().execute.return_value = {
            'items': [{'id': 'primary', 'primary': True}]
        }
        servicio.freebusy().query().execute.side_effect = Exception('timeout de red')

        inicio = slot_futuro()
        resultado = consultar_freebusy(self.host.email, inicio, inicio + timedelta(minutes=30))
        self.assertFalse(resultado)


class CrearEventoGoogleTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    @patch('calendario.google_calendar.services.build')
    @patch('calendario.google_calendar.services.service_account')
    def test_crea_evento_y_guarda_meet_url(self, mock_sa, mock_build):
        from calendario.google_calendar.services import crear_evento_google

        servicio = MagicMock()
        mock_build.return_value = servicio
        mock_sa.Credentials.from_service_account_file.return_value.with_subject.return_value = MagicMock()
        servicio.events().insert().execute.return_value = {
            'id': 'evento-test-123',
            'hangoutLink': 'https://meet.google.com/test-abc',
            'conferenceData': {},
        }

        reserva = _reserva_en_bd(self.host, self.et)
        crear_evento_google(reserva.pk)

        reserva.refresh_from_db()
        self.assertEqual(reserva.google_event_id, 'evento-test-123')
        self.assertEqual(reserva.google_meet_url, 'https://meet.google.com/test-abc')
        self.assertEqual(reserva.google_sync_estado, Reserva.GoogleSyncEstado.SINCRONIZADO)

    @patch('calendario.google_calendar.services.build')
    @patch('calendario.google_calendar.services.service_account')
    def test_error_google_marca_estado_error(self, mock_sa, mock_build):
        from calendario.google_calendar.services import crear_evento_google
        from googleapiclient.errors import HttpError

        servicio = MagicMock()
        mock_build.return_value = servicio
        mock_sa.Credentials.from_service_account_file.return_value.with_subject.return_value = MagicMock()

        resp_mock = MagicMock()
        resp_mock.status = 403
        servicio.events().insert().execute.side_effect = HttpError(resp=resp_mock, content=b'forbidden')

        reserva = _reserva_en_bd(self.host, self.et)
        crear_evento_google(reserva.pk)

        reserva.refresh_from_db()
        self.assertEqual(reserva.google_sync_estado, Reserva.GoogleSyncEstado.ERROR)

    @patch('calendario.google_calendar.services.build')
    @patch('calendario.google_calendar.services.service_account')
    def test_eliminar_evento_idempotente_404(self, mock_sa, mock_build):
        from calendario.google_calendar.services import eliminar_evento_google
        from googleapiclient.errors import HttpError

        servicio = MagicMock()
        mock_build.return_value = servicio
        mock_sa.Credentials.from_service_account_file.return_value.with_subject.return_value = MagicMock()

        resp_mock = MagicMock()
        resp_mock.status = 404
        servicio.events().delete().execute.side_effect = HttpError(resp=resp_mock, content=b'not found')

        reserva = _reserva_en_bd(self.host, self.et)
        reserva.google_event_id = 'evento-ya-borrado'
        reserva.save()

        # No debe lanzar excepción
        eliminar_evento_google(reserva.pk)
