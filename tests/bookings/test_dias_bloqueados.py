"""
Días bloqueados de un tipo de evento: fechas concretas en las que el evento no
se ofrece aunque los organizadores tengan horas libres.

Son del evento, no de las personas: no tocan los horarios ni los demás eventos
de los organizadores. Las fechas se leen en la zona del dueño del evento.
"""
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from calendario.bookings.exceptions import SlotNoDisponibleError
from calendario.bookings.models import Reserva
from calendario.bookings.services import calcular_slots, crear_reserva
from tests.factories import NOMBRE_INVITADO, crear_disponibilidad, crear_event_type, crear_host


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class DiasBloqueadosTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(7):
            crear_disponibilidad(self.host, dia=dia)
        self.tz = ZoneInfo(self.host.timezone)
        self.dia = timezone.now().astimezone(self.tz).date() + timedelta(days=3)

    def _bloquear(self, *dias):
        self.et.fechas_bloqueadas = [d.isoformat() for d in dias]
        self.et.save()

    def _slots(self, desde, hasta=None):
        return calcular_slots(self.et, desde, hasta or desde)

    def test_un_dia_bloqueado_no_ofrece_horas(self, *_):
        self.assertTrue(self._slots(self.dia))
        self._bloquear(self.dia)
        self.assertEqual(self._slots(self.dia), [])

    def test_los_demas_dias_no_se_tocan(self, *_):
        antes = self._slots(self.dia - timedelta(days=1), self.dia + timedelta(days=1))
        self._bloquear(self.dia)
        despues = self._slots(self.dia - timedelta(days=1), self.dia + timedelta(days=1))
        self.assertEqual(
            despues,
            [s for s in antes if s.astimezone(self.tz).date() != self.dia],
        )
        self.assertTrue(despues)

    def test_otro_evento_del_mismo_host_sigue_abierto(self, *_):
        otro = crear_event_type(self.host, nombre='Otro evento')
        self._bloquear(self.dia)
        self.assertTrue(calcular_slots(otro, self.dia, self.dia))

    def test_reservar_en_un_dia_bloqueado_se_rechaza(self, *_):
        hora = self._slots(self.dia)[0]
        self._bloquear(self.dia)
        with self.assertRaises(SlotNoDisponibleError):
            crear_reserva(
                event_type=self.et, inicio_utc=hora,
                nombre_invitado=NOMBRE_INVITADO, email_invitado='invitado@test.com',
            )
        self.assertFalse(Reserva.objects.exists())

    def test_una_fecha_rota_no_tumba_el_calculo(self, *_):
        self.et.fechas_bloqueadas = ['no-es-fecha', self.dia.isoformat()]
        self.et.save()
        self.assertEqual(self._slots(self.dia), [])
        self.assertTrue(self._slots(self.dia + timedelta(days=1)))
