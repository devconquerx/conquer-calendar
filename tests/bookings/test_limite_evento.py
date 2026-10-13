"""
Límite de reservas del evento: «X reservas cada Y días» sumando todos los
invitados de un tipo de evento.

Misma ventana móvil que el límite por invitado, por la fecha de la cita en la
zona del host. Lleno el cupo, los días afectados dejan de ofrecer horas y
`crear_reserva` rechaza lo que llegue tarde con SlotNoDisponibleError.
"""
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from calendario.bookings.exceptions import SlotNoDisponibleError
from calendario.bookings.models import Reserva
from calendario.bookings.services import (
    calcular_slots, crear_reserva, dias_llenos_evento, reemplazar_reserva,
)
from tests.factories import NOMBRE_INVITADO, crear_disponibilidad, crear_event_type, crear_host


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class LimiteEventoTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.unico_por_invitado = False
        self.et.limite_evento = 2
        self.et.limite_evento_dias = 1
        self.et.save()
        for dia in range(7):
            crear_disponibilidad(self.host, dia=dia)
        self.tz = ZoneInfo(self.host.timezone)
        self.dia = timezone.now().astimezone(self.tz).date() + timedelta(days=3)

    def _slots(self, dia):
        return calcular_slots(self.et, dia, dia)

    def _reservar(self, inicio, n):
        return crear_reserva(
            event_type=self.et, inicio_utc=inicio,
            nombre_invitado=NOMBRE_INVITADO, email_invitado=f'invitado{n}@test.com',
        )

    def _reserva_directa(self, dia, **extra):
        inicio = self._slots(dia)[0]
        return Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado=NOMBRE_INVITADO, email_invitado='directa@test.com', **extra,
        )

    def test_dos_cada_un_dia_cierra_el_dia_al_llegar_a_dos(self, *_):
        slots = self._slots(self.dia)
        self._reservar(slots[0], 1)
        self.assertTrue(self._slots(self.dia), 'con una reserva el día sigue abierto')
        self._reservar(slots[-1], 2)
        self.assertEqual(self._slots(self.dia), [])
        self.assertTrue(self._slots(self.dia + timedelta(days=1)), 'el día siguiente no se toca')

    def test_la_tercera_reserva_del_dia_se_rechaza(self, *_):
        slots = self._slots(self.dia)
        self._reservar(slots[0], 1)
        self._reservar(slots[1], 2)
        with self.assertRaises(SlotNoDisponibleError):
            self._reservar(slots[2], 3)
        self.assertEqual(Reserva.objects.count(), 2)

    def test_las_canceladas_no_cuentan(self, *_):
        self._reserva_directa(self.dia, estado=Reserva.Estado.CANCELADA)
        self._reserva_directa(self.dia, estado=Reserva.Estado.CANCELADA)
        self.assertTrue(self._slots(self.dia))

    def test_sin_limite_no_filtra_nada(self, *_):
        self.et.limite_evento = None
        self.et.limite_evento_dias = None
        self.et.save()
        slots = self._slots(self.dia)
        self._reservar(slots[0], 1)
        self._reservar(slots[1], 2)
        self._reservar(slots[2], 3)
        self.assertTrue(self._slots(self.dia))

    def test_ventana_de_varios_dias(self, *_):
        # 2 cada 7: con reservas el día 0 y el 3, queda lleno cualquier día que
        # quepa con las dos en una semana, es decir del -3 al 6. Hacia atrás
        # también: las reservas futuras cierran los días previos.
        self.et.limite_evento_dias = 7
        self.et.save()
        d = self.dia
        self._reserva_directa(d)
        self._reserva_directa(d + timedelta(days=3))
        dias = {n: d + timedelta(days=n) for n in (-4, -3, 1, 6, 7)}
        self.assertEqual(
            dias_llenos_evento(self.et, dias.values()),
            {dias[-3], dias[1], dias[6]},
        )

    def test_reagendar_dentro_de_un_dia_lleno(self, *_):
        # La vieja se cancela antes de contar: moverla de hora no gasta cupo.
        slots = self._slots(self.dia)
        vieja = self._reservar(slots[0], 1)
        self._reservar(slots[1], 2)
        nueva = reemplazar_reserva(
            vieja.pk, self.et, slots[2], NOMBRE_INVITADO, 'invitado1@test.com',
        )
        self.assertEqual(nueva.inicio_utc, slots[2])
        self.assertEqual(Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA).count(), 2)

