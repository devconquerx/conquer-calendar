"""
El límite de reservas cuenta los días en la zona del invitado.

Se contaba en la del dueño del evento, que no tiene por qué ser ni la del alumno
ni la del profesor. Una alumna en Toronto con clase el 5/11 a las 18:00 veía el
aviso «agendada para el 6 de noviembre» porque en Madrid, donde está el dueño, ya
era el 6; y el tope de 14 días le abría el 20/11 en vez del 19/11.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.exceptions import LimiteReservasError
from calendario.bookings.models import Reserva
from calendario.bookings.services import aviso_limite_reservas, comprobar_limite_reservas
from tests.factories import crear_event_type, crear_host

UTC = dt_timezone.utc
EMAIL = 'alumna@x.com'
TORONTO = 'America/Toronto'
# 18:00–18:50 del 5/11 en Toronto; 00:00 del 6/11 en Madrid.
INICIO_CLASE = datetime(2026, 11, 5, 23, 0, tzinfo=UTC)
FIN_CLASE = INICIO_CLASE + timedelta(minutes=50)


def toronto(dia, hora):
    """El `dia` de noviembre de 2026 a esa hora de Toronto (UTC-5), en UTC."""
    return datetime(2026, 11, dia, hora, 0, tzinfo=UTC) + timedelta(hours=5)


class LimiteEnZonaDelInvitadoTest(TestCase):

    def setUp(self):
        self.dueno = crear_host()
        self.dueno.timezone = 'Europe/Madrid'
        self.dueno.save(update_fields=['timezone'])
        self.profesora = crear_host(email='profe@x.com')
        self.profesora.timezone = 'America/Argentina/Ushuaia'
        self.profesora.save(update_fields=['timezone'])
        self.et = crear_event_type(self.dueno)
        self.et.limite_reservas = 1
        self.et.limite_reservas_dias = 14
        self.et.save()
        self.clase = self._reserva()

    def _reserva(self, timezone_invitado=TORONTO, inicio=INICIO_CLASE, host=None, **extra):
        return Reserva.objects.create(
            event_type=self.et, host=host or self.profesora, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=50), nombre_invitado='Alumna',
            email_invitado=extra.pop('email', EMAIL), timezone_invitado=timezone_invitado, **extra,
        )

    def _ahora(self, momento):
        return patch('calendario.bookings.services.timezone.now', return_value=momento)

    def _comprobar(self, inicio, zona=TORONTO, email=EMAIL):
        comprobar_limite_reservas(self.et, inicio, email, timezone_invitado=zona)

    def test_el_dia_14_abre_entero_en_su_zona(self):
        with self._ahora(FIN_CLASE + timedelta(days=1)):
            self._comprobar(toronto(19, 8))

    def test_el_dia_13_sigue_cerrado_hasta_el_final_en_su_zona(self):
        with self._ahora(FIN_CLASE + timedelta(days=1)):
            with self.assertRaises(LimiteReservasError) as ctx:
                self._comprobar(toronto(18, 23))
        self.assertEqual(ctx.exception.disponible_desde, date(2026, 11, 19))

    def test_sin_zona_del_que_reserva_se_usa_la_del_dueno(self):
        """El 19/11 a las 23:30 UTC ya es día 20 en Madrid; a las 22:30, aún 19."""
        with self._ahora(FIN_CLASE + timedelta(days=1)):
            self._comprobar(datetime(2026, 11, 19, 22, 30, tzinfo=UTC), zona='')
            with self.assertRaises(LimiteReservasError):
                self._comprobar(datetime(2026, 11, 18, 22, 30, tzinfo=UTC), zona='')
