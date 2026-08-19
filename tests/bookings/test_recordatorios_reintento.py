"""
Reintento de recordatorios y espaciado de las ráfagas.

Antes el comando marcaba `recordatorio_N_enviado = True` saliera o no el correo,
así que un rebote de Mailgun se traducía en un alumno que nunca recibía su
recordatorio y en una reserva que decía que sí lo había recibido. Con el tope de
ráfaga de Mailgun eso pasaba a diario.

Ahora solo se marca cuando el envío sale, se reintenta en la siguiente pasada del
cron y se deja de insistir tras `MAX_INTENTOS`.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from calendario.bookings.management.commands.enviar_recordatorios import MAX_INTENTOS
from calendario.bookings.models import (
    ConfigCorreoEvento, PlantillaCorreo, Reserva,
)
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO, crear_event_type, crear_host,
)


RUTA_ENVIAR = 'calendario.bookings.management.commands.enviar_recordatorios._enviar'


class RecordatoriosBase(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.plantilla = PlantillaCorreo.objects.create(
            nombre='Recordatorio test',
            texto_encabezado='Recuerda tu sesión',
            cuerpo='Hola {{nombre_invitado}}.',
            recordatorio_1_activo=True,
            recordatorio_1_horas=24,
            recordatorio_2_activo=False,
        )
        ConfigCorreoEvento.objects.create(
            event_type=self.et,
            plantilla_recordatorio=self.plantilla,
        )

    def _reserva(self, horas_para_la_sesion=2):
        inicio = datetime.now(dt_timezone.utc) + timedelta(hours=horas_para_la_sesion)
        return Reserva.objects.create(
            event_type=self.et,
            host=self.host,
            inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.et.duracion_minutos),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
        )


class ReintentoTest(RecordatoriosBase):

    def test_si_el_envio_falla_no_se_marca_como_enviado(self):
        reserva = self._reserva()

        with patch(RUTA_ENVIAR, return_value=False):
            call_command('enviar_recordatorios', pausa=0)

        reserva.refresh_from_db()
        self.assertFalse(reserva.recordatorio_1_enviado)
        self.assertEqual(reserva.recordatorio_1_intentos, 1)

    def test_el_fallo_se_reintenta_en_la_siguiente_pasada_y_acaba_saliendo(self):
        reserva = self._reserva()

        with patch(RUTA_ENVIAR, return_value=False):
            call_command('enviar_recordatorios', pausa=0)
        with patch(RUTA_ENVIAR, return_value=True) as envio_bueno:
            call_command('enviar_recordatorios', pausa=0)

        self.assertEqual(envio_bueno.call_count, 1)
        reserva.refresh_from_db()
        self.assertTrue(reserva.recordatorio_1_enviado)

    def test_si_sale_bien_se_marca_y_no_se_repite(self):
        reserva = self._reserva()

        with patch(RUTA_ENVIAR, return_value=True) as envio:
            call_command('enviar_recordatorios', pausa=0)
            call_command('enviar_recordatorios', pausa=0)

        self.assertEqual(envio.call_count, 1)
        reserva.refresh_from_db()
        self.assertTrue(reserva.recordatorio_1_enviado)

    def test_deja_de_insistir_tras_el_maximo_de_intentos(self):
        # Una dirección rota no debe reintentarse cada 5 minutos hasta que
        # empiece la sesión: gasta cuota de la que van justos.
        reserva = self._reserva()

        with patch(RUTA_ENVIAR, return_value=False) as envio:
            for _ in range(MAX_INTENTOS + 3):
                call_command('enviar_recordatorios', pausa=0)

        self.assertEqual(envio.call_count, MAX_INTENTOS)
        reserva.refresh_from_db()
        self.assertEqual(reserva.recordatorio_1_intentos, MAX_INTENTOS)
        self.assertFalse(reserva.recordatorio_1_enviado)


class EspaciadoTest(RecordatoriosBase):

    def test_el_limite_corta_la_pasada(self):
        for _ in range(6):
            self._reserva()

        with patch(RUTA_ENVIAR, return_value=True) as envio:
            call_command('enviar_recordatorios', limite=4, pausa=0)

        self.assertEqual(envio.call_count, 4)

    def test_lo_que_no_entra_sale_en_la_siguiente_pasada(self):
        for _ in range(6):
            self._reserva()

        with patch(RUTA_ENVIAR, return_value=True) as envio:
            call_command('enviar_recordatorios', limite=4, pausa=0)
            call_command('enviar_recordatorios', limite=4, pausa=0)

        self.assertEqual(envio.call_count, 6)
        self.assertEqual(Reserva.objects.filter(recordatorio_1_enviado=True).count(), 6)

    def test_lo_mas_inminente_se_envia_primero(self):
        # Si el límite corta, el que se queda fuera tiene que ser el de dentro
        # de 20 horas, no el de dentro de 1.
        lejana = self._reserva(horas_para_la_sesion=20)
        inminente = self._reserva(horas_para_la_sesion=1)

        with patch(RUTA_ENVIAR, return_value=True):
            call_command('enviar_recordatorios', limite=1, pausa=0)

        inminente.refresh_from_db()
        lejana.refresh_from_db()
        self.assertTrue(inminente.recordatorio_1_enviado)
        self.assertFalse(lejana.recordatorio_1_enviado)
