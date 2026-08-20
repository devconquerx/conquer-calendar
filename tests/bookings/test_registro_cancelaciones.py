"""
Cada cancelación deja constancia de quién la hizo y desde dónde.

Sale del incidente del 20/08/2026: hubo una tanda de cancelaciones y no se pudo
responder a "¿quién canceló esto?" porque los logs del contenedor se van en cada
despliegue. Los closers no entran a la app, así que cuando una reserva suya
desaparece la respuesta no puede ser "lo hizo el sistema".
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.bookings.models import CancelacionReserva, Reserva
from calendario.bookings.services import cancelar_reserva
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

PATCH_CONFLICTO = 'calendario.bookings.services.hay_conflicto_calendario'
PATCH_CREAR = 'calendario.bookings.services.crear_evento_google'
PATCH_CANCELAR_GCAL = 'calendario.bookings.services.cancelar_evento_google'


@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
class RegistroCancelacionTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(7):
            crear_disponibilidad(self.host, dia=dia)

    def _reserva(self):
        from calendario.bookings.services import crear_reserva
        r = crear_reserva(
            event_type=self.et, inicio_utc=slot_futuro(),
            nombre_invitado='Lead', email_invitado='lead@x.com',
        )
        r.google_event_id = 'gcal-1'
        r.save(update_fields=['google_event_id'])
        return r

    def test_se_guarda_quien_y_desde_donde(self, *_):
        r = self._reserva()
        cancelar_reserva(
            r,
            origen=CancelacionReserva.Origen.PANEL,
            usuario=self.host,
            detalle=self.host.email,
        )
        registro = CancelacionReserva.objects.get(reserva=r)
        self.assertEqual(registro.origen, CancelacionReserva.Origen.PANEL)
        self.assertEqual(registro.usuario, self.host)
        self.assertEqual(registro.detalle, self.host.email)

    def test_sin_origen_queda_como_sin_identificar(self, *_):
        r = self._reserva()
        cancelar_reserva(r)
        registro = CancelacionReserva.objects.get(reserva=r)
        self.assertEqual(registro.origen, CancelacionReserva.Origen.DESCONOCIDO)

    def test_no_duplica_registro_si_ya_estaba_cancelada(self, *_):
        r = self._reserva()
        cancelar_reserva(r, origen=CancelacionReserva.Origen.PANEL)
        cancelar_reserva(r, origen=CancelacionReserva.Origen.COMANDO)
        self.assertEqual(CancelacionReserva.objects.filter(reserva=r).count(), 1)

    def test_avisar_invitado_false_no_manda_correo(self, _crear, _conf, mock_gcal):
        r = self._reserva()
        with self.captureOnCommitCallbacks(execute=True):
            cancelar_reserva(r, avisar_invitado=False)
        mock_gcal.assert_called_once_with(r.pk, avisar_invitado=False)
        self.assertFalse(CancelacionReserva.objects.get(reserva=r).correo_enviado)

    def test_avisar_invitado_true_manda_correo(self, _crear, _conf, mock_gcal):
        r = self._reserva()
        with self.captureOnCommitCallbacks(execute=True):
            cancelar_reserva(r, avisar_invitado=True)
        mock_gcal.assert_called_once_with(r.pk, avisar_invitado=True)
        self.assertTrue(CancelacionReserva.objects.get(reserva=r).correo_enviado)

    def test_la_reserva_queda_cancelada_igual(self, *_):
        r = self._reserva()
        cancelar_reserva(r, origen=CancelacionReserva.Origen.SYNC_GCAL)
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CANCELADA)


class VistaCancelacionesTest(TestCase):
    """La vista es privada: solo los emails de CANCELACIONES_EMAILS_AUTORIZADOS."""

    def setUp(self):
        self.autorizado = crear_host(email='santiago.tovar@conquerx.com')
        self.otro = crear_host(email='otro.persona@conquerx.com', first_name='Otro')

    def test_el_autorizado_entra(self):
        self.client.force_login(self.autorizado)
        with self.settings(CANCELACIONES_EMAILS_AUTORIZADOS=['santiago.tovar@conquerx.com']):
            resp = self.client.get(reverse('panel_reservas:cancelaciones'))
        self.assertEqual(resp.status_code, 200)

    def test_otro_usuario_no_entra(self):
        self.client.force_login(self.otro)
        with self.settings(CANCELACIONES_EMAILS_AUTORIZADOS=['santiago.tovar@conquerx.com']):
            resp = self.client.get(reverse('panel_reservas:cancelaciones'))
        self.assertEqual(resp.status_code, 403)

    def test_sin_login_no_entra(self):
        with self.settings(CANCELACIONES_EMAILS_AUTORIZADOS=['santiago.tovar@conquerx.com']):
            resp = self.client.get(reverse('panel_reservas:cancelaciones'))
        self.assertNotEqual(resp.status_code, 200)


class CorteDeArranqueTest(TestCase):
    """El sync solo cancela reservas creadas después del corte configurado."""

    def test_sin_setting_no_cancela_nada(self):
        from calendario.google_calendar.sync import _fecha_corte_cancelacion
        from django.utils import timezone
        with self.settings(CANCELAR_RECHAZOS_DESDE=''):
            self.assertGreater(_fecha_corte_cancelacion(), timezone.now())

    def test_con_fecha_devuelve_esa_fecha(self):
        from calendario.google_calendar.sync import _fecha_corte_cancelacion
        with self.settings(CANCELAR_RECHAZOS_DESDE='2026-08-20T18:00:00'):
            corte = _fecha_corte_cancelacion()
        self.assertEqual(corte.year, 2026)
        self.assertEqual(corte.month, 8)
        self.assertEqual(corte.day, 20)

    @patch(PATCH_CANCELAR_GCAL)
    @patch(PATCH_CONFLICTO, return_value=False)
    @patch(PATCH_CREAR)
    def test_una_reserva_anterior_al_corte_no_se_cancela(self, *_):
        from calendario.bookings.services import crear_reserva
        from calendario.google_calendar.sync import _cancelar_reservas_rechazadas
        from django.utils import timezone
        from datetime import timedelta

        host = crear_host()
        et = crear_event_type(host)
        for dia in range(7):
            crear_disponibilidad(host, dia=dia)
        r = crear_reserva(
            event_type=et, inicio_utc=slot_futuro(),
            nombre_invitado='Lead', email_invitado='viejo@x.com',
        )
        r.google_event_id = 'gcal-viejo'
        r.save(update_fields=['google_event_id'])
        # La reserva es de ahora; el corte, de mañana -> queda fuera.
        manana = (timezone.now() + timedelta(days=1)).isoformat()
        with self.settings(CANCELAR_RECHAZOS_DESDE=manana):
            _cancelar_reservas_rechazadas(host, ['gcal-viejo'])
        r.refresh_from_db()
        self.assertEqual(r.estado, Reserva.Estado.CONFIRMADA)


class NoAtribuirElRechazoAlHostTest(TestCase):
    """
    Un rechazo en Google no se le atribuye al host.

    Lo único que se sabe es que su invitación figura rechazada; quién lo hizo no
    lo dice la API. En estos calendarios los setters, cuentas antiguas y el grupo
    de toda la empresa tienen permiso de escritura, así que señalar al host es
    acusarle de algo que puede no haber hecho.
    """

    @patch(PATCH_CANCELAR_GCAL)
    @patch(PATCH_CONFLICTO, return_value=False)
    @patch(PATCH_CREAR)
    def test_el_registro_no_señala_al_host(self, *_):
        from calendario.bookings.services import crear_reserva
        from calendario.google_calendar.sync import _cancelar_reservas_rechazadas

        host = crear_host()
        et = crear_event_type(host)
        for dia in range(7):
            crear_disponibilidad(host, dia=dia)
        r = crear_reserva(
            event_type=et, inicio_utc=slot_futuro(),
            nombre_invitado='Lead', email_invitado='lead@x.com',
        )
        r.google_event_id = 'gcal-rechazado'
        r.save(update_fields=['google_event_id'])

        with self.settings(CANCELAR_RECHAZOS_DESDE='2020-01-01T00:00:00'):
            _cancelar_reservas_rechazadas(host, ['gcal-rechazado'])

        registro = CancelacionReserva.objects.get(reserva=r)
        self.assertEqual(registro.origen, CancelacionReserva.Origen.SYNC_GCAL)
        # Nadie firma el rechazo: no se sabe quién fue.
        self.assertIsNone(registro.usuario)
        # Y el texto describe el hecho, no acusa a nadie de haberlo provocado.
        self.assertIn('figura rechazada', registro.detalle)
        self.assertNotIn('rechazó la invitación', registro.detalle)


@patch(PATCH_CANCELAR_GCAL)
@patch(PATCH_CONFLICTO, return_value=False)
@patch(PATCH_CREAR)
class OtraCitaDelMismoLeadTest(TestCase):
    """
    Una cancelación suelta asusta; con la cita nueva al lado, no.

    Cuando un lead reserva otra vez por un enlace distinto en vez de usar el
    botón de reagendar, la app crea una reserva nueva y la vieja se queda
    huérfana: la cancelación aparece sin contexto y el closer cree que ha
    perdido el lead.
    """

    def setUp(self):
        self.host = crear_host(email='santiago.tovar@conquerx.com')
        self.et = crear_event_type(self.host)
        for dia in range(7):
            crear_disponibilidad(self.host, dia=dia)

    def _reserva(self, email, inicio):
        from calendario.bookings.services import crear_reserva
        return crear_reserva(
            event_type=self.et, inicio_utc=inicio,
            nombre_invitado='Lead', email_invitado=email,
        )

    def test_marca_al_lead_que_volvio_a_reservar(self, *_):
        from datetime import timedelta
        vieja = self._reserva('vuelve@x.com', slot_futuro())
        cancelar_reserva(vieja, origen=CancelacionReserva.Origen.SYNC_GCAL)
        nueva = self._reserva('vuelve@x.com', slot_futuro() + timedelta(days=1))

        self.client.force_login(self.host)
        with self.settings(CANCELACIONES_EMAILS_AUTORIZADOS=['santiago.tovar@conquerx.com']):
            resp = self.client.get(reverse('panel_reservas:cancelaciones'))
        fila = resp.context['cancelaciones'][0]
        self.assertEqual(fila.otra_cita, nueva)
        self.assertEqual(resp.context['con_otra_cita'], 1)

    def test_el_que_se_quedo_sin_cita_no_se_marca(self, *_):
        sola = self._reserva('sin_nada@x.com', slot_futuro())
        cancelar_reserva(sola, origen=CancelacionReserva.Origen.SYNC_GCAL)

        self.client.force_login(self.host)
        with self.settings(CANCELACIONES_EMAILS_AUTORIZADOS=['santiago.tovar@conquerx.com']):
            resp = self.client.get(reverse('panel_reservas:cancelaciones'))
        fila = resp.context['cancelaciones'][0]
        self.assertIsNone(fila.otra_cita)
        self.assertEqual(resp.context['con_otra_cita'], 0)
