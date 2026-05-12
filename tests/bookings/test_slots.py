from datetime import date, time, timedelta

from django.test import TestCase

from calendario.bookings.services import calcular_slots
from tests.factories import crear_disponibilidad, crear_event_type, crear_host


class CalcularSlotsTest(TestCase):

    def setUp(self):
        self.host = crear_host()

    def test_sin_disponibilidad_no_hay_slots(self):
        et = crear_event_type(self.host)
        hoy = date.today()
        slots = calcular_slots(et, hoy, hoy + timedelta(days=7))
        self.assertEqual(slots, [])

    def test_slots_dentro_del_bloque(self):
        et = crear_event_type(self.host, duracion=30)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(11, 0))

        lunes = self._proximo_dia(0)
        slots = calcular_slots(et, lunes, lunes)

        # Debe haber al menos 2 slots de 30 min en el bloque de 9:00–11:00
        # Los slots vienen en UTC, la disponibilidad está en la zona del host
        self.assertGreaterEqual(len(slots), 2)

    def test_buffer_despues_reduce_slots(self):
        et_sin_buffer = crear_event_type(self.host, nombre='Sin buffer', duracion=30)
        et_con_buffer = crear_event_type(
            self.host, nombre='Con buffer', duracion=30
        )
        et_con_buffer.buffer_despues_minutos = 30
        et_con_buffer.save()

        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(11, 0))
        lunes = self._proximo_dia(0)

        slots_sin = calcular_slots(et_sin_buffer, lunes, lunes)
        slots_con = calcular_slots(et_con_buffer, lunes, lunes)

        self.assertGreater(len(slots_sin), len(slots_con))

    def test_aviso_minimo_excluye_slots_proximos(self):
        et = crear_event_type(self.host, duracion=30)
        et.aviso_minimo_horas = 48
        et.save()
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(18, 0))
        crear_disponibilidad(self.host, dia=1, inicio=time(9, 0), fin=time(18, 0))

        hoy = date.today()
        manana = hoy + timedelta(days=1)
        slots = calcular_slots(et, hoy, manana)

        # Con 48h de aviso mínimo no debe haber slots en las próximas 48h
        self.assertEqual(slots, [])

    def test_no_hay_slots_en_fin_de_semana_sin_disponibilidad(self):
        et = crear_event_type(self.host, duracion=30)
        # Solo disponibilidad lunes–viernes (0–4)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

        sabado = self._proximo_dia(5)
        domingo = self._proximo_dia(6)
        slots = calcular_slots(et, sabado, domingo)
        self.assertEqual(slots, [])

    @staticmethod
    def _proximo_dia(dia_semana):
        """Devuelve la próxima fecha que sea el día de semana indicado (0=lunes)."""
        hoy = date.today()
        dias = (dia_semana - hoy.weekday()) % 7 or 7
        return hoy + timedelta(days=dias)
