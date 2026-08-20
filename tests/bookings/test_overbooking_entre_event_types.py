"""
Las reglas free/busy se evalúan contra las palabras del tipo de evento que se
está CONSULTANDO, no las del tipo con el que se creó la reserva que ya está en
la agenda. Es como funciona Calendly: las reglas viven en el event type que el
invitado tiene delante y se comparan contra el título de lo que hay en el
calendario conectado, venga de donde venga.

Reproduce el caso real de producción: una reserva creada desde
'Reagendada - Conquer Blocks USA' (tipo SIN reglas) bloqueaba el hueco para
'⭐ Sesión de Consultoría | Conquer Blocks LATAM' (tipo que SÍ reconoce la
palabra "Reagendada" en el título), porque se miraba `permite_overbooking`, que
el sync calcula con las palabras del tipo de la reserva.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.exceptions import SlotNoDisponibleError
from calendario.bookings.models import Reserva
from calendario.bookings.services import calcular_slots
from calendario.bookings.services import crear_reserva as svc_crear
from calendario.google_calendar.models import GoogleCalendarEvento
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

PATCH_CONFLICTO = 'calendario.bookings.services.hay_conflicto_calendario'
PATCH_EVENTO = 'calendario.bookings.services.crear_evento_google'
PATCH_BUSY_LOCAL = 'calendario.bookings.services._obtener_busy_intervalos_con_fallback'


def _reservar(et, inicio, email):
    return svc_crear(
        event_type=et, inicio_utc=inicio,
        nombre_invitado='Lead', email_invitado=email,
    )


@patch(PATCH_BUSY_LOCAL, return_value=[])
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_EVENTO)
class ReglasDelTipoConsultadoTest(TestCase):
    """
    Dos tipos de evento sobre el mismo host:
      - `et_sin_reglas`: crea la reserva. No tiene ninguna palabra configurada.
      - `et_que_reconoce`: tiene 'Reagendada' como regla y consulta el hueco.
    """

    def setUp(self):
        self.host = crear_host()
        self.et_sin_reglas = crear_event_type(
            self.host, nombre='Reagendada - Conquer Blocks USA', duracion=30)
        self.et_que_reconoce = crear_event_type(
            self.host, nombre='⭐ Sesión de Consultoría | Conquer Blocks LATAM',
            duracion=30)
        self.et_que_reconoce.gcal_palabras_ignorar = 'Reagendada'
        self.et_que_reconoce.save(update_fields=['gcal_palabras_ignorar'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _reserva_con_evento(self, inicio, titulo, et=None, email='a@x.com'):
        """Crea la reserva y su evento en la copia local de Google Calendar."""
        r = _reservar(et or self.et_sin_reglas, inicio, email)
        r.google_event_id = f'gcal-{r.pk}'
        r.save(update_fields=['google_event_id'])
        GoogleCalendarEvento.objects.create(
            host=self.host,
            google_event_id=r.google_event_id,
            titulo=titulo,
            inicio_utc=r.inicio_utc,
            fin_utc=r.fin_utc,
        )
        return r

    def _dia_de(self, inicio):
        return inicio.date()

    def test_el_tipo_que_reconoce_la_palabra_ve_el_hueco(self, *_):
        inicio = slot_futuro()
        r = self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Reagendada - Conquer Blocks USA')
        # El flag sigue en False: su tipo de evento no tiene reglas.
        self.assertFalse(r.permite_overbooking)

        dia = self._dia_de(inicio)
        slots = calcular_slots(self.et_que_reconoce, dia, dia)
        self.assertIn(inicio, slots)

    def test_un_tipo_sin_reglas_sigue_viendo_el_hueco_ocupado(self, *_):
        inicio = slot_futuro()
        self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Reagendada - Conquer Blocks USA')

        dia = self._dia_de(inicio)
        slots = calcular_slots(self.et_sin_reglas, dia, dia)
        self.assertNotIn(inicio, slots)

    def test_titulo_que_no_matchea_sigue_bloqueando(self, *_):
        inicio = slot_futuro()
        self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Conquer Blocks USA')

        dia = self._dia_de(inicio)
        slots = calcular_slots(self.et_que_reconoce, dia, dia)
        self.assertNotIn(inicio, slots)

    def test_se_puede_reservar_encima_desde_el_tipo_que_reconoce(self, *_):
        inicio = slot_futuro()
        primera = self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Reagendada - Conquer Blocks USA')

        segunda = _reservar(self.et_que_reconoce, inicio, 'b@x.com')

        self.assertEqual(segunda.inicio_utc, inicio)
        # La restricción de unicidad solo admite una exclusiva por (host, inicio):
        # es la nueva la que renuncia a la exclusividad.
        self.assertTrue(segunda.permite_overbooking)
        primera.refresh_from_db()
        self.assertFalse(primera.permite_overbooking)
        self.assertEqual(
            Reserva.objects.filter(
                host=self.host, inicio_utc=inicio,
                estado=Reserva.Estado.CONFIRMADA).count(),
            2,
        )

    def test_no_se_puede_reservar_encima_desde_un_tipo_que_no_reconoce(self, *_):
        inicio = slot_futuro()
        self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Reagendada - Conquer Blocks USA')

        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et_sin_reglas, inicio, 'b@x.com')

    def test_el_tope_de_dos_sigue_cerrando_el_horario(self, *_):
        inicio = slot_futuro()
        self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Reagendada - Conquer Blocks USA')
        _reservar(self.et_que_reconoce, inicio, 'b@x.com')

        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et_que_reconoce, inicio, 'c@x.com')

    def test_sin_evento_en_la_copia_local_manda_el_flag(self, *_):
        """
        Reserva cuyo evento aún no se ha sincronizado: no hay título que comparar,
        así que se respeta `permite_overbooking` como respaldo.
        """
        inicio = slot_futuro()
        r = _reservar(self.et_sin_reglas, inicio, 'a@x.com')
        # La reserva no llegó a tener evento propio en la copia local.
        self.assertFalse(
            GoogleCalendarEvento.objects
            .filter(host=self.host, google_event_id=r.google_event_id)
            .exists()
        )

        dia = self._dia_de(inicio)
        self.assertNotIn(inicio, calcular_slots(self.et_que_reconoce, dia, dia))

        r.permite_overbooking = True
        r.save(update_fields=['permite_overbooking'])
        self.assertIn(inicio, calcular_slots(self.et_que_reconoce, dia, dia))

    def test_el_emoji_pegado_a_otra_palabra_tambien_libera(self, *_):
        """El match es substring: no hace falta que la marca vaya separada."""
        self.et_que_reconoce.gcal_palabras_ignorar = '⏰'
        self.et_que_reconoce.save(update_fields=['gcal_palabras_ignorar'])
        inicio = slot_futuro()
        self._reserva_con_evento(inicio, 'Carlos y Brandon⏰ Conquer Blocks USA')

        dia = self._dia_de(inicio)
        self.assertIn(inicio, calcular_slots(self.et_que_reconoce, dia, dia))

    def test_otro_horario_no_se_ve_afectado(self, *_):
        inicio = slot_futuro()
        otro = inicio + timedelta(hours=2)
        self._reserva_con_evento(
            inicio, 'Lead y Santiago Tovar - Reagendada - Conquer Blocks USA')

        dia = self._dia_de(inicio)
        slots = calcular_slots(self.et_sin_reglas, dia, dia)
        self.assertIn(otro, slots)
