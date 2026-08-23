from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from calendario.availability.models import BloqueHorarioSemanal
from calendario.bookings.models import Reserva
from calendario.bookings.services import calcular_slots
from tests.factories import crear_disponibilidad, crear_event_type, crear_host

TZ = 'America/Bogota'
PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'


class CalcularSlotsTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        # El post_save de User (users/signals.py) le da a todo host nuevo
        # disponibilidad de lunes a viernes de 00:00 a 23:59. Es el default de
        # onboarding, para que un host recién creado no aparezca con la agenda
        # en blanco. Aquí estorba: estos tests miden el cálculo sobre la
        # disponibilidad que define cada uno, así que se parte de cero.
        BloqueHorarioSemanal.objects.filter(host=self.host).delete()

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
        # El buffer no recorta el final de la jornada: solo separa una cita de
        # la siguiente, igual que Calendly. Con la agenda vacía no quita ni un
        # slot, así que para verlo hace falta una reserva de por medio.
        et = crear_event_type(self.host, duracion=30)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(11, 0))
        lunes = self._proximo_dia(0)

        inicio = datetime.combine(lunes, time(9, 0)).replace(
            tzinfo=ZoneInfo(self.host.timezone))
        Reserva.objects.create(
            event_type=et, host=self.host,
            inicio_utc=inicio, fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado='Previa', email_invitado='previa@x.com',
        )

        slots_sin = calcular_slots(et, lunes, lunes)
        et.buffer_despues_minutos = 30
        et.save()
        slots_con = calcular_slots(et, lunes, lunes)

        # Sin buffer quedan 9:30, 10:00 y 10:30; con media hora de margen
        # detrás de la reserva, las 9:30 desaparecen.
        self.assertGreater(len(slots_sin), len(slots_con))

    def test_aviso_minimo_excluye_slots_proximos(self):
        et = crear_event_type(self.host, duracion=30)
        et.aviso_minimo_minutos = 48 * 60
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


@patch(PATCH_BUSY, return_value=[])
class GridAlignmentTest(TestCase):
    """
    Verifica que los slots respeten el grid del incremento incluso cuando un
    evento ocupado termina a mitad de intervalo.
    Ejemplo: bloque 10:00-13:00, busy 10:00-11:30, incremento 60min, duración 50min
    → debe salir 12:00 (grid), NO 11:30 (off-grid).
    """

    def setUp(self):
        from datetime import datetime, timezone as tz_utc
        self.host = crear_host(email='host.grid@test.com')
        self.host.timezone = TZ
        self.host.save(update_fields=['timezone'])
        BloqueHorarioSemanal.objects.filter(host=self.host).delete()
        # Lunes próximo como ancla (siempre ordenado)
        hoy = date.today()
        dias = (7 - hoy.weekday()) % 7 or 7
        self.lunes = hoy + timedelta(days=dias)
        crear_disponibilidad(self.host, dia=0, inicio=time(10, 0), fin=time(13, 0))
        self.et = crear_event_type(self.host, nombre='Grid Test', duracion=50)
        self.et.incremento_inicio_minutos = 60
        self.et.buffer_antes_minutos = 0
        self.et.buffer_despues_minutos = 0
        self.et.aviso_minimo_minutos = 0
        self.et.save()

    def _busy(self, hi, hf):
        """Genera un intervalo busy en UTC a partir de horas locales del lunes."""
        from datetime import datetime, timezone as tz_utc
        tz = ZoneInfo(TZ)
        inicio = datetime.combine(self.lunes, hi).replace(tzinfo=tz).astimezone(ZoneInfo('UTC'))
        fin = datetime.combine(self.lunes, hf).replace(tzinfo=tz).astimezone(ZoneInfo('UTC'))
        return [(inicio, fin)]

    def _horas(self, slots):
        tz = ZoneInfo(TZ)
        return sorted(s.astimezone(tz).strftime('%H:%M') for s in slots)

    def test_busy_a_mitad_de_intervalo_respeta_grid(self, _busy_mock):
        # Busy 10:00-11:30 → primer slot libre sería 11:30 off-grid, debe salir 12:00
        from calendario.bookings.services import _calcular_slots_para_host
        busy = self._busy(time(10, 0), time(11, 30))
        slots = _calcular_slots_para_host(self.et, self.host, self.lunes, self.lunes, busy_override=busy)
        self.assertEqual(self._horas(slots), ['12:00'])

    def test_sin_busy_slots_en_punto(self, _busy_mock):
        # Sin conflictos: 10:00, 11:00, 12:00
        from calendario.bookings.services import _calcular_slots_para_host
        slots = _calcular_slots_para_host(self.et, self.host, self.lunes, self.lunes, busy_override=[])
        self.assertEqual(self._horas(slots), ['10:00', '11:00', '12:00'])

    def test_busy_exactamente_en_limite_de_grid_no_desplaza(self, _busy_mock):
        # Busy 10:00-11:00 (justo en el límite): siguiente slot en grid = 11:00
        from calendario.bookings.services import _calcular_slots_para_host
        busy = self._busy(time(10, 0), time(11, 0))
        slots = _calcular_slots_para_host(self.et, self.host, self.lunes, self.lunes, busy_override=busy)
        self.assertEqual(self._horas(slots), ['11:00', '12:00'])
