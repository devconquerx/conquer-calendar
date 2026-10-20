"""
Cancelación tardía dentro del límite de reservas por invitado.

La política de la academia: una clase cancelada con menos de 24 h de antelación
se pierde. Sin esto, con «1 cada 12 días» el alumno cancelaba una hora antes,
la reserva dejaba de contar y podía reservar otra al momento.

Con `limite_cancelacion_horas` la reserva que el propio invitado cancela —desde
su enlace, reagendando o rechazando en Google— dentro de ese margen sigue
contando para su tope. La que cancela el host o el panel, no.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from calendario.bookings.exceptions import LimiteReservasError, ReservaDuplicadaError
from calendario.bookings.models import CancelacionReserva, Reserva
from calendario.bookings.services import (
    aviso_limite_reservas, cancelar_reserva, crear_reserva, reemplazar_reserva,
)
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

Origen = CancelacionReserva.Origen


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class CancelacionTardiaTest(TestCase):

    TELEFONO = '+34 600123456'

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.unico_por_invitado = False
        self.et.limite_reservas = 1
        self.et.limite_reservas_dias = 30
        self.et.limite_cancelacion_horas = 24
        self.et.save()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _cita(self, dentro_de):
        """Reserva confirmada que empieza dentro de `dentro_de` (timedelta)."""
        inicio = (timezone.now() + dentro_de).replace(second=0, microsecond=0)
        return Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=30),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
            telefono_invitado=self.TELEFONO,
        )

    def _reservar(self, inicio):
        return crear_reserva(
            event_type=self.et, inicio_utc=inicio,
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
            telefono_invitado=self.TELEFONO,
        )

    def _reagendar(self, vieja, inicio):
        return reemplazar_reserva(
            reserva_vieja_pk=vieja.pk, event_type=self.et, inicio_utc=inicio,
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
            telefono_invitado=self.TELEFONO,
        )

    def test_cancelar_desde_su_enlace_a_ultima_hora_sigue_contando(self, *_):
        cancelar_reserva(self._cita(timedelta(hours=2)), origen=Origen.PUBLICA)
        with self.assertRaises(LimiteReservasError):
            self._reservar(slot_futuro(dias=3))

    def test_rechazar_en_google_a_ultima_hora_sigue_contando(self, *_):
        cancelar_reserva(self._cita(timedelta(hours=2)), origen=Origen.RECHAZO_INVITADO)
        with self.assertRaises(LimiteReservasError):
            self._reservar(slot_futuro(dias=3))

    def test_cancelar_con_antelacion_devuelve_la_plaza(self, *_):
        cancelar_reserva(self._cita(timedelta(days=2)), origen=Origen.PUBLICA)
        self._reservar(slot_futuro(dias=3))

    def test_si_cancela_el_host_o_el_panel_no_cuenta(self, *_):
        cancelar_reserva(self._cita(timedelta(hours=2)), origen=Origen.SYNC_GCAL)
        cancelar_reserva(self._cita(timedelta(hours=3)), origen=Origen.PANEL)
        self._reservar(slot_futuro(dias=3))

    def test_sin_horas_configuradas_las_canceladas_no_cuentan(self, *_):
        self.et.limite_cancelacion_horas = None
        self.et.save()
        cancelar_reserva(self._cita(timedelta(hours=2)), origen=Origen.PUBLICA)
        self._reservar(slot_futuro(dias=3))

    def test_reagendar_a_ultima_hora_no_cabe_y_conserva_la_cita(self, *_):
        vieja = self._cita(timedelta(hours=2))
        with self.assertRaises(LimiteReservasError):
            self._reagendar(vieja, slot_futuro(dias=3))
        vieja.refresh_from_db()
        self.assertEqual(vieja.estado, Reserva.Estado.CONFIRMADA)
        self.assertFalse(vieja.cancelaciones.exists())

    def test_reagendar_con_antelacion_sigue_funcionando(self, *_):
        vieja = self._cita(timedelta(days=2))
        nueva = self._reagendar(vieja, slot_futuro(dias=3))
        self.assertEqual(nueva.estado, Reserva.Estado.CONFIRMADA)

    def test_a_ultima_hora_no_se_ofrece_cambiar_la_reserva_que_tiene(self, *_):
        self.et.unico_por_invitado = True
        self.et.save()
        self._cita(timedelta(hours=2))
        with self.assertRaises(LimiteReservasError):
            self._reservar(slot_futuro(dias=3))

    def test_con_antelacion_se_sigue_ofreciendo_cambiarla(self, *_):
        self.et.unico_por_invitado = True
        self.et.save()
        self._cita(timedelta(days=2))
        with self.assertRaises(ReservaDuplicadaError):
            self._reservar(slot_futuro(dias=3))

    def test_el_aviso_dice_que_la_cita_que_tapa_esta_cancelada(self, *_):
        cancelar_reserva(self._cita(timedelta(hours=2)), origen=Origen.PUBLICA)
        aviso = aviso_limite_reservas(self.et, EMAIL_INVITADO, self.TELEFONO)
        self.assertTrue(aviso['cancelada'])
        self.assertFalse(aviso['cita_futura'])

    def test_el_aviso_de_una_cita_confirmada_no_cambia(self, *_):
        self._cita(timedelta(days=2))
        aviso = aviso_limite_reservas(self.et, EMAIL_INVITADO, self.TELEFONO)
        self.assertFalse(aviso['cancelada'])
        self.assertTrue(aviso['cita_futura'])

    def test_sin_limite_de_reservas_no_se_puede_poner(self, *_):
        self.et.limite_reservas = None
        self.et.limite_reservas_dias = None
        with self.assertRaises(ValidationError):
            self.et.full_clean()


class FormularioPanelTest(TestCase):

    def test_se_configura_desde_el_formulario_del_tipo_de_evento(self):
        from calendario.event_types.forms import EventTypeForm
        form = EventTypeForm(data=dict(
            nombre='Clase 1 a 1', duracion_minutos=45, incremento_inicio_minutos=15,
            aviso_minimo_minutos=0, aviso_maximo_dias=60, confirmacion_tipo='default',
            crm_destino='none', limite_reservas=1, limite_reservas_dias=12,
            limite_cancelacion_horas=24,
        ))
        form.instance.host = crear_host()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().limite_cancelacion_horas, 24)
