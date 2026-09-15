"""
Límite de reservas por invitado: «X reservas cada Y días» en un tipo de evento.

La ventana es móvil y cuenta por la fecha de la cita en la zona del host: con 1
cada 30 días, quien tuvo cita el 10/09 puede volver a tenerla el 10/10. Con una
reserva futura y «Solo una reserva por invitado» se sigue ofreciendo cambiarla;
superado el tope, se manda a la página de máximo alcanzado.
"""
from datetime import date, timedelta

from django.test import TestCase

from calendario.bookings.services import _excede_limite


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
