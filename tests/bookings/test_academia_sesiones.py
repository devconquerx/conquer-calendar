"""
Registro de las clases 1 a 1 en la academia.

La academia es la que tiene que responder «¿cuántas sesiones dio este profesor
en agosto?», y el histórico no puede vivir en este calendario porque las
reservas viejas se acabarán limpiando. Así que cada reserva de un tipo de evento
marcado se le envía al LMS.

Lo que cubren estos tests, en orden:

  * los tipos de evento sin la marca no mandan nada a la academia (que es el
    caso de casi todas las ~500 agendas diarias);
  * la sesión sale con el profesor, el alumno y el horario que la academia
    necesita, y con el id del alumno que el propio LMS firmó en el token;
  * cancelar y reagendar también se avisan: sin eso el dashboard contaría clases
    que nunca se dieron;
  * sin configurar, no se llama a nadie —una academia caída no puede impedir que
    un alumno reserve—;
  * y un endpoint que responde 200 con un error dentro NO se da por bueno, que
    es la forma silenciosa de perder justo el dato que se quiere medir.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from calendario.bookings.conversions.services import academia
from calendario.bookings.models import Reserva
from calendario.event_types.models import EventType
from calendario.users.models import User
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, crear_reserva, slot_futuro,
)


URL_ACADEMIA = 'https://academia.example.com/graphql/'
API_KEY = 'clave-de-la-academia'

UID_ALUMNO = 4321
ID_ACADEMIA = 7


CONFIG_ACADEMIA = dict(
    ACADEMIA_ENABLED=True,
    ACADEMIA_GRAPHQL_URL=URL_ACADEMIA,
    ACADEMIA_API_KEY=API_KEY,
    ACADEMIA_TIMEOUT_SECONDS=15,
)


class RespuestaFalsa:
    """Lo mínimo de `requests.Response` que mira el servicio."""

    def __init__(self, cuerpo=None, status_code=200, texto=''):
        self.status_code = status_code
        self._cuerpo = cuerpo if cuerpo is not None else {
            'data': {'syncCalendarSession': {'success': True, 'created': True, 'errors': []}}
        }
        self.text = texto or str(self._cuerpo)

    def json(self):
        return self._cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


def _mock_gcal():
    return [
        patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False),
        patch('calendario.bookings.services.crear_evento_google'),
        patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[]),
    ]


@override_settings(**CONFIG_ACADEMIA)
class PayloadSesionTest(TestCase):
    """Qué se le manda a la academia por cada sesión."""

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host, nombre='Clase 1 a 1 de inglés', duracion=45)
        self.et.registrar_en_academia = True
        self.et.academia_lms_id = ID_ACADEMIA
        self.et.save(update_fields=['registrar_en_academia', 'academia_lms_id'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _reserva(self, **kwargs):
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            reserva = crear_reserva(self.et)
        if kwargs:
            for campo, valor in kwargs.items():
                setattr(reserva, campo, valor)
            reserva.save(update_fields=list(kwargs))
        return reserva

    def test_payload_lleva_profesor_alumno_y_horario(self):
        reserva = self._reserva(alumno_lms_uid=str(UID_ALUMNO))
        payload = academia.construir_payload(reserva)

        self.assertEqual(payload['reservationId'], str(reserva.pk))
        self.assertEqual(payload['status'], 'confirmed')
        self.assertEqual(payload['academyId'], ID_ACADEMIA)
        self.assertEqual(payload['professorEmail'], self.host.email.lower())
        self.assertEqual(payload['studentLmsId'], str(UID_ALUMNO))
        self.assertEqual(payload['studentEmail'], EMAIL_INVITADO.lower())
        self.assertEqual(payload['eventTypeName'], 'Clase 1 a 1 de inglés')
        self.assertEqual(payload['startsAt'], reserva.inicio_utc.isoformat())
        self.assertEqual(payload['endsAt'], reserva.fin_utc.isoformat())

    def test_no_se_manda_nada_mas(self):
        """Lo acordado es el profesor, el evento y cuándo fue. Cada campo de más
        es uno que hay que mantener sincronizado entre dos aplicaciones y que
        alguien acabará usando; añadir uno más adelante cuesta menos que quitarlo
        cuando ya se usa."""
        payload = academia.construir_payload(self._reserva())
        self.assertEqual(set(payload), {
            'reservationId', 'status', 'academyId',
            'professorEmail', 'studentLmsId', 'studentEmail',
            'eventTypeName', 'startsAt', 'endsAt',
        })

    def test_envio_va_al_endpoint_con_la_clave(self):
        reserva = self._reserva()
        with patch('calendario.bookings.conversions.services.academia.requests.post',
                   return_value=RespuestaFalsa()) as mock_post:
            academia.push_sesion(reserva)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], URL_ACADEMIA)
        self.assertEqual(kwargs['headers']['X-API-Key'], API_KEY)
        self.assertEqual(kwargs['json']['variables']['input']['reservationId'], str(reserva.pk))

    def test_sin_id_de_academia_viaja_null(self):
        """El id de la academia es opcional a propósito: sin él la sesión sigue
        saliendo y la resuelve el LMS por el profesor. Bloquear el envío por un
        id interno del otro lado dejaría la integración parada por nada."""
        self.et.academia_lms_id = None
        self.et.save(update_fields=['academia_lms_id'])
        reserva = self._reserva()
        self.assertIsNone(academia.construir_payload(reserva)['academyId'])

    def test_una_cancelada_viaja_como_cancelada(self):
        reserva = self._reserva(estado=Reserva.Estado.CANCELADA)
        self.assertEqual(academia.construir_payload(reserva)['status'], 'cancelled')


class EstadoTraducidoTest(TestCase):
    """El LMS usa claves en inglés en sus choices; el vocabulario nuestro se
    queda de este lado de la frontera."""

    def test_el_mapa_cubre_los_dos_estados_de_reserva(self):
        self.assertEqual(
            set(academia.ESTADOS),
            {Reserva.Estado.CONFIRMADA.value, Reserva.Estado.CANCELADA.value},
        )


class SinConfigurarTest(TestCase):
    """Una academia caída o a medio configurar no puede romper nada de aquí."""

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.registrar_en_academia = True
        self.et.save(update_fields=['registrar_en_academia'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            self.reserva = crear_reserva(self.et)

    @override_settings(ACADEMIA_ENABLED=False, ACADEMIA_GRAPHQL_URL=URL_ACADEMIA,
                       ACADEMIA_API_KEY=API_KEY)
    def test_apagada_no_llama(self):
        with patch('calendario.bookings.conversions.services.academia.requests.post') as mock_post:
            academia.push_sesion(self.reserva)
        mock_post.assert_not_called()

    @override_settings(ACADEMIA_ENABLED=True, ACADEMIA_GRAPHQL_URL='', ACADEMIA_API_KEY=API_KEY)
    def test_sin_url_no_llama(self):
        with patch('calendario.bookings.conversions.services.academia.requests.post') as mock_post:
            academia.push_sesion(self.reserva)
        mock_post.assert_not_called()

    @override_settings(ACADEMIA_ENABLED=True, ACADEMIA_GRAPHQL_URL=URL_ACADEMIA, ACADEMIA_API_KEY='')
    def test_sin_clave_no_llama(self):
        with patch('calendario.bookings.conversions.services.academia.requests.post') as mock_post:
            academia.push_sesion(self.reserva)
        mock_post.assert_not_called()


@override_settings(**CONFIG_ACADEMIA)
class ErroresDelEndpointTest(TestCase):
    """GraphQL devuelve 200 aunque la mutación falle: el error va en el cuerpo."""

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.registrar_en_academia = True
        self.et.save(update_fields=['registrar_en_academia'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            self.reserva = crear_reserva(self.et)

    def test_errors_en_el_cuerpo_no_se_da_por_bueno(self):
        cuerpo = {'errors': [{'message': 'Profesor no registrado'}], 'data': None}
        with patch('calendario.bookings.conversions.services.academia.requests.post',
                   return_value=RespuestaFalsa(cuerpo)):
            with self.assertRaises(RuntimeError):
                academia.push_sesion(self.reserva)

    def test_success_false_no_se_da_por_bueno(self):
        cuerpo = {'data': {'syncCalendarSession': {
            'success': False, 'created': False, 'errors': ['Professor not registered'],
        }}}
        with patch('calendario.bookings.conversions.services.academia.requests.post',
                   return_value=RespuestaFalsa(cuerpo)):
            with self.assertRaises(RuntimeError):
                academia.push_sesion(self.reserva)

    def test_http_500_revienta(self):
        with patch('calendario.bookings.conversions.services.academia.requests.post',
                   return_value=RespuestaFalsa(status_code=500, texto='boom')):
            with self.assertRaises(RuntimeError):
                academia.push_sesion(self.reserva)


@override_settings(**CONFIG_ACADEMIA)
class DespachoTest(TestCase):
    """Qué reservas se le mandan a la academia y cuáles no."""

    def setUp(self):
        self.host = crear_host()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _event_type(self, registrar, nombre):
        et = crear_event_type(self.host, nombre=nombre)
        et.registrar_en_academia = registrar
        et.save(update_fields=['registrar_en_academia'])
        return et

    def _crear(self, et, inicio=None):
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            return crear_reserva(et, inicio_utc=inicio)

    def test_evento_sin_marcar_no_va_a_la_academia(self):
        et = self._event_type(False, 'Llamada de ventas')
        reserva = self._crear(et)
        with patch('calendario.bookings.tasks.process_academia_sesion.delay') as mock_delay:
            from calendario.bookings.tasks import dispatch_schedule_tasks
            with patch('calendario.bookings.tasks.process_schedule_supabase.delay'):
                dispatch_schedule_tasks(reserva.pk)
        mock_delay.assert_not_called()

    def test_evento_marcado_se_encola(self):
        et = self._event_type(True, 'Clase 1 a 1')
        reserva = self._crear(et)
        # dispatch_schedule_tasks ya corrió al crear la reserva y dejó su guard
        # puesto, así que se limpia para poder observar el despacho.
        reserva.tags.remove('sch_tasks_dispatched')
        with patch('calendario.bookings.tasks.process_academia_sesion.delay') as mock_delay:
            from calendario.bookings.tasks import dispatch_schedule_tasks
            with patch('calendario.bookings.tasks.process_schedule_supabase.delay'):
                dispatch_schedule_tasks(reserva.pk)
        mock_delay.assert_called_once_with(reserva.pk)

    def test_la_tarea_respeta_la_marca_aunque_se_encole_de_mas(self):
        et = self._event_type(False, 'Webinar')
        reserva = self._crear(et)
        from calendario.bookings.tasks import process_academia_sesion
        with patch('calendario.bookings.conversions.services.academia.requests.post') as mock_post:
            process_academia_sesion(reserva.pk)
        mock_post.assert_not_called()

    def test_cancelar_avisa_a_la_academia(self):
        et = self._event_type(True, 'Clase 1 a 1')
        reserva = self._crear(et)
        from calendario.bookings.services import cancelar_reserva
        with patch('calendario.bookings.tasks.process_academia_cancelacion.delay') as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                cancelar_reserva(reserva)
        mock_delay.assert_called_once_with(reserva.pk)

    def test_cancelar_un_evento_sin_marcar_no_avisa(self):
        et = self._event_type(False, 'Llamada de ventas')
        reserva = self._crear(et)
        from calendario.bookings.services import cancelar_reserva
        with patch('calendario.bookings.tasks.process_academia_cancelacion.delay') as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                cancelar_reserva(reserva)
        mock_delay.assert_not_called()

    def test_eliminar_avisa_con_el_payload_ya_armado(self):
        """Borrar una reserva desde el panel no deja fila que consultar después,
        así que el aviso a la academia se arma antes de borrar. Sin esto la
        sesión se quedaría allí como confirmada para siempre."""
        et = self._event_type(True, 'Clase 1 a 1')
        reserva = self._crear(et)
        reserva_pk = reserva.pk

        from calendario.bookings.services import eliminar_reserva
        with patch('calendario.bookings.tasks.process_academia_borrado.delay') as mock_delay, \
             patch('calendario.bookings.services._eliminar_google_event_directo'):
            with self.captureOnCommitCallbacks(execute=True):
                eliminar_reserva(reserva)

        mock_delay.assert_called_once()
        payload = mock_delay.call_args[0][0]
        self.assertEqual(payload['reservationId'], str(reserva_pk))
        self.assertEqual(payload['status'], 'cancelled')
        self.assertFalse(Reserva.objects.filter(pk=reserva_pk).exists())

    def test_reagendar_cancela_la_vieja_y_da_de_alta_la_nueva(self):
        """Reagendar son dos sesiones distintas para la academia: la vieja se
        cancela y la nueva se da de alta. Si solo llegara el alta, el profesor
        aparecería con dos clases donde dio una."""
        et = self._event_type(True, 'Clase 1 a 1')
        vieja = self._crear(et)
        nuevo_inicio = slot_futuro(dias=3)

        from calendario.bookings.services import reemplazar_reserva
        with patch('calendario.bookings.tasks.process_academia_cancelacion.delay') as mock_cancel, \
             patch('calendario.bookings.tasks.process_academia_sesion.delay') as mock_alta, \
             patch('calendario.bookings.tasks.process_schedule_supabase.delay'), \
             patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False), \
             patch('calendario.bookings.services.crear_evento_google'), \
             patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[]):
            with self.captureOnCommitCallbacks(execute=True):
                nueva = reemplazar_reserva(
                    reserva_vieja_pk=vieja.pk,
                    event_type=et,
                    inicio_utc=nuevo_inicio,
                    nombre_invitado=NOMBRE_INVITADO,
                    email_invitado=EMAIL_INVITADO,
                )

        mock_cancel.assert_called_once_with(vieja.pk)
        mock_alta.assert_called_once_with(nueva.pk)


class UidEnElPayloadTest(TestCase):
    """El id del alumno que guarda la reserva es lo que viaja a la academia.

    Que se guarde al reservar desde el iframe lo cubre `test_embed_lms.py`; aquí
    solo importa que no se quede por el camino.
    """

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host, nombre='Clase 1 a 1')
        self.et.registrar_en_academia = True
        self.et.save(update_fields=['registrar_en_academia'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def test_el_uid_guardado_llega_al_payload(self):
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            reserva = crear_reserva(self.et)
        reserva.alumno_lms_uid = str(UID_ALUMNO)
        reserva.save(update_fields=['alumno_lms_uid'])

        self.assertEqual(academia.construir_payload(reserva)['studentLmsId'], str(UID_ALUMNO))

    def test_sin_uid_viaja_vacio(self):
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            reserva = crear_reserva(self.et)
        self.assertEqual(academia.construir_payload(reserva)['studentLmsId'], '')


class MarcaEnElPanelTest(TestCase):
    """La casilla del panel es lo que decide qué se le manda a la academia, así
    que tiene que sobrevivir a un guardado del formulario completo."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='academia.admin@test.com', username='academia_admin',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.et = EventType.objects.create(
            host=self.admin, nombre='Clase 1 a 1 de inglés', duracion_minutos=45,
        )
        self.url = reverse('panel_event_types:event_type_update', args=[self.et.pk])

    def _post(self, **extra):
        datos = {
            'nombre': self.et.nombre,
            'descripcion': '',
            'duracion_minutos': 45,
            'incremento_inicio_minutos': 30,
            'buffer_antes_minutos': 0,
            'buffer_despues_minutos': 0,
            'aviso_minimo_minutos': 0,
            'aviso_maximo_dias': 60,
            'crm_destino': 'none',
            'confirmacion_tipo': 'default',
            'confirmacion_url': '',
            'gcal_palabras_ignorar': '',
            'activo': 'on',
        }
        datos.update(extra)
        c = Client()
        c.force_login(self.admin)
        return c.post(self.url, datos)

    def test_marcar_la_casilla_la_guarda(self):
        self._post(registrar_en_academia='on')
        self.et.refresh_from_db()
        self.assertTrue(self.et.registrar_en_academia)

    def test_desmarcarla_la_quita(self):
        self.et.registrar_en_academia = True
        self.et.save(update_fields=['registrar_en_academia'])
        self._post()
        self.et.refresh_from_db()
        self.assertFalse(self.et.registrar_en_academia)


@override_settings(**CONFIG_ACADEMIA)
class ReenvioManualTest(TestCase):
    """El comando de reenvío tapa huecos de un rango concreto. El histórico
    anterior a la integración no se sube: las sesiones se registran de aquí en
    adelante."""

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.registrar_en_academia = True
        self.et.save(update_fields=['registrar_en_academia'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        mocks = _mock_gcal()
        with mocks[0], mocks[1], mocks[2]:
            self.reserva = crear_reserva(self.et)

    def test_sin_rango_no_manda_nada(self):
        with patch('calendario.bookings.tasks.process_academia_sesion.delay') as mock_delay:
            with self.assertRaises(CommandError):
                call_command('enviar_sesiones_academia')
        mock_delay.assert_not_called()

    def test_con_rango_encola_lo_de_ese_rango(self):
        desde = (self.reserva.inicio_utc - timedelta(days=1)).strftime('%Y-%m-%d')
        with patch('calendario.bookings.tasks.process_academia_sesion.delay') as mock_delay:
            call_command('enviar_sesiones_academia', desde=desde)
        mock_delay.assert_called_once_with(self.reserva.pk)

    def test_el_rango_deja_fuera_lo_anterior(self):
        desde = (self.reserva.inicio_utc + timedelta(days=30)).strftime('%Y-%m-%d')
        with patch('calendario.bookings.tasks.process_academia_sesion.delay') as mock_delay:
            call_command('enviar_sesiones_academia', desde=desde)
        mock_delay.assert_not_called()
