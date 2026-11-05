"""
Recordatorios por SMS: un SMS como máximo por recordatorio, mensaje por tipo de
evento con uno por defecto, y horas propias o las mismas del correo.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import Mock, patch

import requests
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from calendario.bookings import sms
from calendario.bookings.models import ConfigCorreoEvento, LogSMS, PlantillaCorreo, Reserva
from calendario.event_types.forms import EventTypeForm
from calendario.users.models import User
from tests.factories import EMAIL_INVITADO, crear_event_type, crear_host


TELEFONO = '+34612345678'
CONFIG = dict(
    LABSMOBILE_USERNAME='usuario', LABSMOBILE_API_TOKEN='token',
    LABSMOBILE_SENDER='ConquerPass', LABSMOBILE_TEST=False,
    SITE_URL='https://calendar.conquerx.com',
)


def respuesta(status=200, code='0'):
    return Mock(status_code=status, text='', json=Mock(return_value={'code': code, 'message': 'x', 'subid': 'abc'}))


class TextoTest(TestCase):

    def test_quita_tildes_y_emojis_pero_conserva_lo_que_cabe_en_gsm(self):
        self.assertEqual(sms.limpiar_texto('Raúl Núñez, ¿vienes? 👍 “sí”'), 'Raul Nuñez, ¿vienes?  "si"')

    def test_el_mensaje_por_defecto_es_valido(self):
        sms.validar_plantilla(sms.MENSAJE_POR_DEFECTO)

    @override_settings(**CONFIG)
    def test_un_nombre_larguisimo_no_saca_el_mensaje_de_un_sms_ni_rompe_el_enlace(self):
        valores = sms.valores_de_ejemplo()
        valores['nombre_evento'] = 'Evento ' * 40
        mensaje = sms.componer_mensaje(sms.MENSAJE_POR_DEFECTO, valores)
        self.assertLessEqual(sms.longitud_sms(mensaje), 160)
        self.assertTrue(mensaje.endswith(valores['link_reagendar']))

    def test_rechaza_variables_inexistentes_y_textos_que_no_caben(self):
        with self.assertRaisesMessage(ValidationError, '{{inventada}}'):
            sms.validar_plantilla('Hola {{inventada}}')
        with self.assertRaisesMessage(ValidationError, 'No cabe'):
            sms.validar_plantilla('x' * 161)

    def test_los_caracteres_extendidos_cuentan_doble(self):
        self.assertEqual(sms.longitud_sms('€['), 4)

    def test_telefono(self):
        self.assertEqual(sms.normalizar_telefono('+34 612 34 56 78'), '34612345678')
        self.assertEqual(sms.normalizar_telefono('34612345678'), '34612345678')
        self.assertEqual(sms.normalizar_telefono('123'), '')


@override_settings(**CONFIG)
class EnvioTest(TestCase):

    def _enviar(self, **kwargs):
        with patch.object(sms.requests, 'post', **kwargs) as post:
            return sms.enviar_sms('34612345678', 'Hola'), post

    def test_payload_sin_long_ni_ucs2(self):
        resultado, post = self._enviar(return_value=respuesta())
        self.assertTrue(resultado.ok)
        self.assertEqual(post.call_args.kwargs['json'], {
            'message': 'Hola', 'tpoa': 'ConquerPass', 'recipient': [{'msisdn': '34612345678'}],
        })
        self.assertEqual(post.call_args.kwargs['auth'], ('usuario', 'token'))

    @override_settings(LABSMOBILE_TEST=True)
    def test_modo_prueba(self):
        _, post = self._enviar(return_value=respuesta())
        self.assertEqual(post.call_args.kwargs['json']['test'], '1')

    def test_http_200_con_codigo_de_error_no_cuenta_como_enviado(self):
        resultado, _ = self._enviar(return_value=respuesta(code='27'))
        self.assertFalse(resultado.ok)
        self.assertFalse(resultado.reintentable)

    def test_sin_saldo_detiene_la_pasada(self):
        self.assertTrue(self._enviar(return_value=respuesta(status=402))[0].detener_pasada)

    def test_tiempo_de_lectura_agotado_no_se_reintenta(self):
        resultado, _ = self._enviar(side_effect=requests.exceptions.ReadTimeout())
        self.assertFalse(resultado.reintentable)

    def test_sin_conexion_si_se_reintenta(self):
        resultado, _ = self._enviar(side_effect=requests.exceptions.ConnectTimeout())
        self.assertTrue(resultado.reintentable)
