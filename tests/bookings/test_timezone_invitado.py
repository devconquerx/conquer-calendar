"""
Tests para el fix de zona horaria del visitante en la página de confirmación.

Problema original: la confirmación siempre mostraba la hora en la TZ del host,
ignorando la TZ que el visitante eligió al reservar.

Escenario base: host en America/Bogota (UTC-5), visitante elige America/Caracas (UTC-4).
"""
from datetime import datetime, timezone as dt_timezone, timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.bookings.services import crear_reserva as svc_crear_reserva
from tests.factories import (
    crear_host, crear_event_type, crear_disponibilidad, slot_futuro,
    EMAIL_INVITADO, NOMBRE_INVITADO,
)

TZ_HOST = 'America/Bogota'        # UTC-5
TZ_VISITANTE = 'America/Caracas'  # UTC-4  (1 hora adelante de Bogotá)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _crear_host_bogota():
    host = crear_host(email='host.bogota@test.com', first_name='Host', last_name='Bogota')
    host.timezone = TZ_HOST
    host.save(update_fields=['timezone'])
    return host


def _reserva_directa(event_type, host, inicio_utc, timezone_invitado=''):
    """Crea una Reserva en BD sin pasar por disponibilidad ni Google Calendar.
    Útil para testear la vista de confirmación con fechas arbitrarias."""
    return Reserva.objects.create(
        event_type=event_type,
        host=host,
        inicio_utc=inicio_utc,
        fin_utc=inicio_utc + timedelta(minutes=event_type.duracion_minutos),
        nombre_invitado=NOMBRE_INVITADO,
        email_invitado=EMAIL_INVITADO,
        timezone_invitado=timezone_invitado,
    )


# ---------------------------------------------------------------------------
# 1. Servicio: crear_reserva guarda timezone_invitado
# ---------------------------------------------------------------------------

class CrearReservaTimezoneTest(TestCase):

    def setUp(self):
        self.host = _crear_host_bogota()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_guarda_timezone_invitado_cuando_se_provee(self, mock_busy, mock_gcal, mock_freebusy):
        """crear_reserva persiste el timezone_invitado que se le pasa."""
        reserva = svc_crear_reserva(
            event_type=self.et,
            inicio_utc=slot_futuro(),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
            timezone_invitado=TZ_VISITANTE,
        )
        self.assertEqual(reserva.timezone_invitado, TZ_VISITANTE)

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_timezone_invitado_vacio_por_defecto(self, mock_busy, mock_gcal, mock_freebusy):
        """Si no se pasa timezone_invitado, el campo queda vacío (reservas viejas)."""
        reserva = svc_crear_reserva(
            event_type=self.et,
            inicio_utc=slot_futuro(),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
            # sin timezone_invitado
        )
        self.assertEqual(reserva.timezone_invitado, '')

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_timezone_invitado_persiste_en_bd(self, mock_busy, mock_gcal, mock_freebusy):
        """El valor guardado en BD se recupera igual."""
        reserva = svc_crear_reserva(
            event_type=self.et,
            inicio_utc=slot_futuro(),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
            timezone_invitado=TZ_VISITANTE,
        )
        desde_bd = Reserva.objects.get(pk=reserva.pk)
        self.assertEqual(desde_bd.timezone_invitado, TZ_VISITANTE)


# ---------------------------------------------------------------------------
# 2. Vista: ConfirmacionView muestra la hora en la TZ correcta
#    (Reservas creadas directamente en BD para evitar ventana de disponibilidad)
# ---------------------------------------------------------------------------

class ConfirmacionViewTimezoneTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = _crear_host_bogota()
        self.et = crear_event_type(self.host)

    def _url_confirmacion(self, token):
        return reverse('public_token:confirmacion', kwargs={'token': token})

    def test_confirmacion_usa_tz_del_visitante(self):
        """
        Si el visitante reservó en America/Caracas (UTC-4),
        la confirmación debe mostrar la hora en Caracas, no en Bogotá (UTC-5).
        15:00 UTC = 11:00 Caracas = 10:00 Bogotá.
        """
        inicio_utc = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        reserva = _reserva_directa(self.et, self.host, inicio_utc, TZ_VISITANTE)

        resp = self.client.get(self._url_confirmacion(reserva.confirmacion_token))

        self.assertEqual(resp.status_code, 200)
        inicio_local = resp.context['inicio_local']
        self.assertEqual(inicio_local.hour, 11,
            f"Esperaba 11h (Caracas) pero se obtuvo {inicio_local.hour}h")
        self.assertEqual(str(resp.context['tz_host']), TZ_VISITANTE)

    def test_confirmacion_hora_es_visitante_no_host(self):
        """
        La hora mostrada NO es la del host.
        Host Bogotá (UTC-5): 15 UTC = 10h.
        Visitante Caracas (UTC-4): 15 UTC = 11h.
        """
        inicio_utc = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        reserva = _reserva_directa(self.et, self.host, inicio_utc, TZ_VISITANTE)

        resp = self.client.get(self._url_confirmacion(reserva.confirmacion_token))
        inicio_local = resp.context['inicio_local']

        self.assertNotEqual(inicio_local.hour, 10,
            "La hora es la del host (Bogotá=10h), debería ser la del visitante (Caracas=11h)")
        self.assertEqual(inicio_local.hour, 11)

    def test_confirmacion_fallback_a_tz_host_para_reservas_viejas(self):
        """
        Reservas antiguas tienen timezone_invitado=''.
        La confirmación debe caer al fallback del host sin romper nada.
        15 UTC → 10 Bogotá (UTC-5).
        """
        inicio_utc = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        reserva = _reserva_directa(self.et, self.host, inicio_utc, timezone_invitado='')

        self.assertEqual(reserva.timezone_invitado, '')

        resp = self.client.get(self._url_confirmacion(reserva.confirmacion_token))

        self.assertEqual(resp.status_code, 200)
        inicio_local = resp.context['inicio_local']
        self.assertEqual(inicio_local.hour, 10,
            f"Fallback al host (Bogotá=10h) pero se obtuvo {inicio_local.hour}h")
        self.assertEqual(str(resp.context['tz_host']), TZ_HOST)

    def test_confirmacion_fin_local_correcto(self):
        """fin_local también se convierte a la TZ del visitante.
        Reunión 30 min: 15:00–15:30 UTC = 11:00–11:30 Caracas."""
        inicio_utc = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        reserva = _reserva_directa(self.et, self.host, inicio_utc, TZ_VISITANTE)

        resp = self.client.get(self._url_confirmacion(reserva.confirmacion_token))
        fin_local = resp.context['fin_local']

        self.assertEqual(fin_local.hour, 11)
        self.assertEqual(fin_local.minute, 30)

    def test_confirmacion_responde_200_y_muestra_nombre(self):
        """La página carga sin errores y muestra el nombre del invitado."""
        reserva = _reserva_directa(self.et, self.host, slot_futuro(), TZ_VISITANTE)
        resp = self.client.get(self._url_confirmacion(reserva.confirmacion_token))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, NOMBRE_INVITADO)

    def test_confirmacion_no_rompe_con_tz_invalida(self):
        """Si timezone_invitado contiene un valor inválido/corrupto, cae al host sin 500."""
        inicio_utc = datetime(2030, 6, 10, 15, 0, tzinfo=dt_timezone.utc)
        reserva = _reserva_directa(self.et, self.host, inicio_utc, 'TZ_INVALIDA_XYZ')

        resp = self.client.get(self._url_confirmacion(reserva.confirmacion_token))

        # No debe lanzar 500; usa fallback al host
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context['tz_host']), 'TZ_INVALIDA_XYZ')
        # La hora es la del host (fallback)
        self.assertEqual(resp.context['inicio_local'].hour, 10)


# ---------------------------------------------------------------------------
# 3. Vista: BookingFormView guarda la TZ del visitante al crear la reserva
# ---------------------------------------------------------------------------

class BookingFormViewTimezoneTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = _crear_host_bogota()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _url_submit(self):
        return reverse('public_booking:booking_submit', kwargs={
            'user_slug': self.host.slug,
            'event_type_slug': self.et.slug,
        })

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_post_guarda_tz_visitante_desde_query_param(self, mock_busy, mock_gcal, mock_freebusy):
        """?tz=America/Caracas en la URL → reserva guardada con esa TZ."""
        inicio_utc = slot_futuro(dias=3, hora=14)
        url = self._url_submit() + f'?tz={TZ_VISITANTE}'

        resp = self.client.post(url, {
            'inicio_utc': inicio_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': EMAIL_INVITADO,
            'telefono_invitado': '+58 4241234567',
        })

        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.filter(email_invitado=EMAIL_INVITADO).last()
        self.assertIsNotNone(reserva)
        self.assertEqual(reserva.timezone_invitado, TZ_VISITANTE)

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_post_guarda_tz_visitante_desde_post_body(self, mock_busy, mock_gcal, mock_freebusy):
        """tz en el body del POST → también se guarda correctamente."""
        inicio_utc = slot_futuro(dias=3, hora=15)

        resp = self.client.post(self._url_submit(), {
            'inicio_utc': inicio_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': EMAIL_INVITADO,
            'telefono_invitado': '+58 4241234567',
            'tz': TZ_VISITANTE,
        })

        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.filter(email_invitado=EMAIL_INVITADO).last()
        self.assertEqual(reserva.timezone_invitado, TZ_VISITANTE)

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_regionalos', return_value=[], create=True)
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_post_sin_tz_usa_tz_host_como_fallback(self, mock_busy, *args):
        """Si no se envía tz, el fallback es la TZ del host."""
        inicio_utc = slot_futuro(dias=3, hora=16)

        resp = self.client.post(self._url_submit(), {
            'inicio_utc': inicio_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': EMAIL_INVITADO,
            'telefono_invitado': '+58 4241234567',
            # sin tz
        })

        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.filter(email_invitado=EMAIL_INVITADO).last()
        self.assertEqual(reserva.timezone_invitado, TZ_HOST)


# ---------------------------------------------------------------------------
# 4. Flujo completo: POST al form → redirect → confirmación con TZ correcta
# ---------------------------------------------------------------------------

class FlujoCompletoTimezoneTest(TestCase):
    """
    Simula el flujo real: visitante venezolano reserva con su TZ
    y ve la confirmación con la hora en Venezuela.
    """

    def setUp(self):
        self.client = Client()
        self.host = _crear_host_bogota()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    @patch('calendario.bookings.services.consultar_freebusy', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    @patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
    def test_flujo_venezolano_en_mexico(self, mock_busy, mock_gcal, mock_freebusy):
        """
        Visitante: está en México pero seleccionó America/Caracas.
        Slot: slot_futuro() a las 14h UTC = 10h Caracas (UTC-4) / 09h Bogotá (UTC-5).
        La confirmación debe mostrar 10h Caracas.
        """
        inicio_utc = slot_futuro(dias=3, hora=14)
        # 14:00 UTC → 10:00 Caracas (UTC-4) → 09:00 Bogotá (UTC-5)
        hora_esperada_caracas = inicio_utc.astimezone(
            __import__('zoneinfo').ZoneInfo(TZ_VISITANTE)
        ).hour

        url_submit = reverse('public_booking:booking_submit', kwargs={
            'user_slug': self.host.slug,
            'event_type_slug': self.et.slug,
        }) + f'?tz={TZ_VISITANTE}'

        resp_post = self.client.post(url_submit, {
            'inicio_utc': inicio_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': EMAIL_INVITADO,
            'telefono_invitado': '+58 4241234567',
        })

        # 1. El POST redirige a confirmación
        self.assertEqual(resp_post.status_code, 302,
            f"Se esperaba redirect 302, se obtuvo {resp_post.status_code}")

        # 2. La reserva tiene la TZ del visitante
        reserva = Reserva.objects.get(email_invitado=EMAIL_INVITADO)
        self.assertEqual(reserva.timezone_invitado, TZ_VISITANTE)

        # 3. La página de confirmación muestra la hora en Caracas
        url_conf = reverse('public_token:confirmacion',
                           kwargs={'token': reserva.confirmacion_token})
        resp_conf = self.client.get(url_conf)

        self.assertEqual(resp_conf.status_code, 200)
        inicio_local = resp_conf.context['inicio_local']
        self.assertEqual(inicio_local.hour, hora_esperada_caracas,
            f"Esperaba {hora_esperada_caracas}h (Caracas) pero se muestra {inicio_local.hour}h")
        self.assertEqual(str(resp_conf.context['tz_host']), TZ_VISITANTE)
