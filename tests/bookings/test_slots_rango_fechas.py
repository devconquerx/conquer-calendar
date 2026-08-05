"""
El rango de fechas concreto recorta los slots que se ofrecen.

`ventana_reservas` decide la ventana, pero el corte de verdad está en el cálculo
de slots: la vista pública ya no pinta esos días, y aquí es donde se comprueba
que una petición hecha a mano tampoco los consigue.
"""
from datetime import date, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from calendario.event_types.models import EventType
from tests.factories import crear_disponibilidad, crear_event_type, crear_host

PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'


@patch(PATCH_BUSY, return_value=[])
class SlotsConRangoDeFechasTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='rango.slots@test.com')
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.et = crear_event_type(self.host, duracion=30)
        # Un lunes de la semana que viene y el lunes siguiente, dentro del rolling
        # de 60 días por defecto: sin rango los dos tienen horas.
        self.lunes = self._proximo_lunes()
        self.otro_lunes = self.lunes + timedelta(days=7)

    def _proximo_lunes(self):
        d = date.today() + timedelta(days=1)
        while d.weekday() != 0:
            d += timedelta(days=1)
        return d

    def _slots(self, desde, hasta):
        from calendario.bookings.services import calcular_slots
        return calcular_slots(self.et, desde, hasta)

    def _fijar_rango(self, inicio, fin):
        self.et.rango_tipo = EventType.RANGO_FECHAS
        self.et.rango_fecha_inicio = inicio
        self.et.rango_fecha_fin = fin
        self.et.save(update_fields=['rango_tipo', 'rango_fecha_inicio', 'rango_fecha_fin'])

    def test_sin_rango_ambos_lunes_tienen_horas(self, _busy):
        self.assertTrue(self._slots(self.lunes, self.lunes))
        self.assertTrue(self._slots(self.otro_lunes, self.otro_lunes))

    def test_el_rango_corta_por_arriba(self, _busy):
        self._fijar_rango(date.today(), self.lunes)
        self.assertTrue(self._slots(self.lunes, self.lunes))
        self.assertEqual(self._slots(self.otro_lunes, self.otro_lunes), [])

    def test_el_rango_corta_por_abajo(self, _busy):
        self._fijar_rango(self.otro_lunes, self.otro_lunes + timedelta(days=30))
        self.assertEqual(self._slots(self.lunes, self.lunes), [])
        self.assertTrue(self._slots(self.otro_lunes, self.otro_lunes))

    def test_pedir_todo_el_periodo_solo_devuelve_lo_de_dentro(self, _busy):
        self._fijar_rango(self.otro_lunes, self.otro_lunes)
        slots = self._slots(self.lunes, self.otro_lunes + timedelta(days=7))
        self.assertTrue(slots)
        # Agrupadas en la zona del host, que es en la que se define el rango.
        tz_host = ZoneInfo(self.host.timezone)
        fechas = {s.astimezone(tz_host).date() for s in slots}
        self.assertEqual(fechas, {self.otro_lunes})

    def test_un_rango_ya_terminado_no_deja_ninguna_hora(self, _busy):
        ayer = date.today() - timedelta(days=1)
        self._fijar_rango(ayer - timedelta(days=30), ayer)
        self.assertEqual(self._slots(self.lunes, self.otro_lunes), [])
