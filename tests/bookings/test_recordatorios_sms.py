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
