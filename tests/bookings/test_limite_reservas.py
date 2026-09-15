"""
Límite de reservas por invitado: «X reservas cada Y días» en un tipo de evento.

La ventana es móvil y cuenta por la fecha de la cita en la zona del host: con 1
cada 30 días, quien tuvo cita el 10/09 puede volver a tenerla el 10/10. Con una
reserva futura y «Solo una reserva por invitado» se sigue ofreciendo cambiarla;
superado el tope, se manda a la página de máximo alcanzado.
"""
from datetime import date, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from calendario.bookings.exceptions import LimiteReservasError, ReservaDuplicadaError
from calendario.bookings.models import Reserva
from calendario.bookings.services import _excede_limite, crear_reserva, reemplazar_reserva
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)


class VentanaTest(TestCase):
    """La cuenta en sí, sin base de datos."""

    def d(self, dia):
        return date(2026, 9, 1) + timedelta(days=dia)

    def test_uno_cada_treinta_dias_vuelve_a_abrir_el_mismo_dia_del_mes_siguiente(self):
        citas = [date(2026, 9, 10)]
        self.assertTrue(_excede_limite(citas, date(2026, 10, 9), 1, 30))
        self.assertFalse(_excede_limite(citas, date(2026, 10, 10), 1, 30))
        # Hacia atrás igual: una cita futura también cierra los días previos.
        self.assertTrue(_excede_limite(citas, date(2026, 8, 12), 1, 30))
        self.assertFalse(_excede_limite(citas, date(2026, 8, 11), 1, 30))

    def test_con_tope_mayor_que_uno_solo_cuenta_lo_que_cabe_en_una_ventana(self):
        # 0 y 40 nunca están en la misma ventana de 30 días con el 20: cada
        # ventana que contiene el 20 tiene como mucho dos citas.
        self.assertFalse(_excede_limite([self.d(0), self.d(40)], self.d(20), 2, 30))
        # 0 y 29 sí caben con el 15 en una sola ventana: serían tres.
        self.assertTrue(_excede_limite([self.d(0), self.d(29)], self.d(15), 2, 30))

    def test_sin_citas_siempre_cabe(self):
        self.assertFalse(_excede_limite([], self.d(0), 1, 1))


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class ServicioTest(TestCase):

    TELEFONO = '+34 600123456'

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.unico_por_invitado = False
        self.et.limite_reservas = 1
        self.et.limite_reservas_dias = 30
        self.et.save()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.tz = ZoneInfo(self.host.timezone)

    def _reservar(self, inicio, email=EMAIL_INVITADO, telefono=TELEFONO):
        return crear_reserva(
            event_type=self.et, inicio_utc=inicio,
            nombre_invitado=NOMBRE_INVITADO, email_invitado=email,
            telefono_invitado=telefono,
        )

    def _cita_pasada(self, hace_dias, email=EMAIL_INVITADO, telefono=TELEFONO, **extra):
        inicio = (timezone.now() - timedelta(days=hace_dias)).replace(minute=0, second=0, microsecond=0)
        return Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=email,
            telefono_invitado=telefono, **extra,
        )

    def test_dentro_de_la_ventana_no_deja_reservar_y_dice_desde_cuando(self, *_):
        pasada = self._cita_pasada(10)
        with self.assertRaises(LimiteReservasError) as ctx:
            self._reservar(slot_futuro(dias=1))
        self.assertEqual(
            ctx.exception.disponible_desde,
            pasada.inicio_utc.astimezone(self.tz).date() + timedelta(days=30),
        )
        self.assertEqual(Reserva.objects.count(), 1)

    def test_fuera_de_la_ventana_reserva_normal(self, *_):
        self._cita_pasada(10)
        self._reservar(slot_futuro(dias=25))
        self.assertEqual(Reserva.objects.count(), 2)

    def test_las_canceladas_no_cuentan(self, *_):
        self._cita_pasada(10, estado=Reserva.Estado.CANCELADA)
        self._reservar(slot_futuro(dias=1))

    def test_otra_persona_no_se_ve_afectada(self, *_):
        self._cita_pasada(10)
        self._reservar(slot_futuro(dias=1), email='otra@x.com', telefono='+34 699999999')

    def test_el_mismo_telefono_con_otro_email_cuenta_como_la_misma_persona(self, *_):
        self._cita_pasada(10)
        with self.assertRaises(LimiteReservasError):
            self._reservar(slot_futuro(dias=1), email='otro-email@x.com')

    def test_hasta_el_tope_puede_tener_varias_futuras(self, *_):
        self.et.limite_reservas = 2
        self.et.save()
        self._reservar(slot_futuro(dias=1))
        self._reservar(slot_futuro(dias=3))
        with self.assertRaises(LimiteReservasError):
            self._reservar(slot_futuro(dias=5))

    def test_sin_limite_configurado_no_hace_nada(self, *_):
        self.et.limite_reservas = None
        self.et.limite_reservas_dias = None
        self.et.save()
        self._cita_pasada(10)
        self._reservar(slot_futuro(dias=1))

    def test_con_reserva_futura_se_ofrece_cambiarla_si_cabe(self, *_):
        self.et.unico_por_invitado = True
        self.et.save()
        self._reservar(slot_futuro(dias=1))
        with self.assertRaises(ReservaDuplicadaError):
            self._reservar(slot_futuro(dias=3))

    def test_con_reserva_futura_no_se_ofrece_cambiarla_si_ni_asi_cabe(self, *_):
        self.et.unico_por_invitado = True
        self.et.save()
        self._cita_pasada(10)
        # La futura se cuela a mano: es la que tendría de antes de poner el límite.
        Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=slot_futuro(dias=2),
            fin_utc=slot_futuro(dias=2) + timedelta(minutes=30),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
            telefono_invitado=self.TELEFONO,
        )
        with self.assertRaises(LimiteReservasError):
            self._reservar(slot_futuro(dias=4))

    def test_reagendar_no_cuenta_la_reserva_que_se_sustituye(self, *_):
        vieja = self._reservar(slot_futuro(dias=1))
        nueva = reemplazar_reserva(
            reserva_vieja_pk=vieja.pk, event_type=self.et, inicio_utc=slot_futuro(dias=3),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
            telefono_invitado=self.TELEFONO,
        )
        self.assertEqual(nueva.estado, Reserva.Estado.CONFIRMADA)

    def test_hacen_falta_los_dos_datos(self, *_):
        self.et.limite_reservas_dias = None
        with self.assertRaises(ValidationError):
            self.et.full_clean()


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class VistasTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.limite_reservas = 1
        self.et.limite_reservas_dias = 30
        self.et.save()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        inicio = timezone.now() - timedelta(days=10)
        Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
        )

    def test_pagina_publica_redirige_a_maximo_alcanzado(self, *_):
        resp = self.client.post(
            reverse('public_booking:booking_submit', kwargs={
                'user_slug': self.host.slug, 'event_type_slug': self.et.slug,
            }),
            {
                'inicio_utc': slot_futuro(dias=1).isoformat(),
                'nombre_invitado': NOMBRE_INVITADO,
                'email_invitado': EMAIL_INVITADO,
                'telefono_invitado': '+34 600123456',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('public_token:limite_reservas'), resp.url)
        self.assertIn(f'evento={self.et.pk}', resp.url)
        self.assertIn('desde=', resp.url)

        pagina = self.client.get(resp.url)
        self.assertContains(pagina, 'has alcanzado el número máximo de reservas')
        self.assertContains(pagina, 'como máximo')
        self.assertContains(pagina, 'Podrás volver a reservar a partir del')

    def test_la_pagina_aguanta_una_url_a_mano(self, *_):
        resp = self.client.get(reverse('public_token:limite_reservas') + '?evento=abc&desde=ayer')
        self.assertContains(resp, 'Inténtalo más adelante')
