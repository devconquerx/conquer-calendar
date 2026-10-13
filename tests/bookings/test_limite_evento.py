"""
Límite de reservas del evento: «X reservas cada Y días» sumando todos los
invitados de un tipo de evento.

Misma ventana móvil que el límite por invitado, por la fecha de la cita en la
zona del host. Lleno el cupo, los días afectados dejan de ofrecer horas y
`crear_reserva` rechaza lo que llegue tarde con SlotNoDisponibleError.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from calendario.bookings.models import Reserva
from calendario.bookings.services import calcular_slots, dias_llenos_evento
from tests.factories import NOMBRE_INVITADO, crear_disponibilidad, crear_event_type, crear_host


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

    def _reserva_directa(self, dia, **extra):
        inicio = self._slots(dia)[0]
        return Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado=NOMBRE_INVITADO, email_invitado='directa@test.com', **extra,
        )

    def test_ventana_de_varios_dias(self):
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
