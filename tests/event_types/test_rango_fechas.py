"""
Tests del rango de fechas concreto de un tipo de evento.

Hasta dónde se puede reservar tiene dos modos excluyentes (como en Calendly):
`rolling`, los próximos N días desde ahora, y `fechas`, un rango fijo con día de
inicio y de fin. El modo por defecto es el rolling, así que los eventos que ya
existían no cambian de comportamiento.

`EventType.ventana_reservas()` es el único sitio donde se decide la ventana; el
resto (cálculo de slots y vistas públicas) la consume.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from calendario.event_types.models import EventType
from calendario.users.models import User
from tests.factories import crear_host


def _et(host, **extra):
    datos = dict(
        nombre='Evento con rango', duracion_minutos=30,
        aviso_maximo_dias=60, incremento_inicio_minutos=30, activo=True,
    )
    datos.update(extra)
    return EventType.objects.create(host=host, **datos)


class VentanaReservasTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='rango.host@test.com')
        self.hoy = date(2026, 3, 10)

    def test_rolling_es_el_modo_por_defecto(self):
        et = _et(self.host)
        self.assertEqual(et.rango_tipo, EventType.RANGO_ROLLING)
        self.assertFalse(et.usa_rango_de_fechas)

    def test_rolling_cuenta_los_dias_desde_hoy(self):
        et = _et(self.host, aviso_maximo_dias=30)
        self.assertEqual(
            et.ventana_reservas(self.hoy),
            (self.hoy, self.hoy + timedelta(days=30)),
        )

    def test_rango_de_fechas_manda_sobre_los_dias(self):
        # aviso_maximo_dias sigue guardado pero no se usa en este modo.
        et = _et(
            self.host, aviso_maximo_dias=365,
            rango_tipo=EventType.RANGO_FECHAS,
            rango_fecha_inicio=date(2026, 4, 1),
            rango_fecha_fin=date(2026, 4, 30),
        )
        self.assertEqual(
            et.ventana_reservas(self.hoy),
            (date(2026, 4, 1), date(2026, 4, 30)),
        )

    def test_el_rango_no_abre_el_pasado(self):
        # El rango empezó hace un mes: se puede reservar desde hoy, no desde antes.
        et = _et(
            self.host, rango_tipo=EventType.RANGO_FECHAS,
            rango_fecha_inicio=date(2026, 2, 1),
            rango_fecha_fin=date(2026, 4, 30),
        )
        self.assertEqual(
            et.ventana_reservas(self.hoy),
            (self.hoy, date(2026, 4, 30)),
        )

    def test_un_rango_ya_terminado_deja_la_ventana_vacia(self):
        et = _et(
            self.host, rango_tipo=EventType.RANGO_FECHAS,
            rango_fecha_inicio=date(2026, 1, 1),
            rango_fecha_fin=date(2026, 1, 31),
        )
        minimo, maximo = et.ventana_reservas(self.hoy)
        self.assertLess(maximo, minimo)

    def test_el_ultimo_dia_del_rango_entra(self):
        et = _et(
            self.host, rango_tipo=EventType.RANGO_FECHAS,
            rango_fecha_inicio=self.hoy,
            rango_fecha_fin=self.hoy,
        )
        self.assertEqual(et.ventana_reservas(self.hoy), (self.hoy, self.hoy))

    def test_modo_fechas_sin_fechas_cae_al_rolling(self):
        # Fila a medias (construida a mano o migrada): no debe dar una ventana rota.
        et = _et(self.host, rango_tipo=EventType.RANGO_FECHAS, aviso_maximo_dias=30)
        self.assertFalse(et.usa_rango_de_fechas)
        self.assertEqual(
            et.ventana_reservas(self.hoy),
            (self.hoy, self.hoy + timedelta(days=30)),
        )


class ValidacionRangoTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='rango.valida@test.com')

    def test_el_modo_fechas_exige_las_dos_fechas(self):
        et = _et(self.host, rango_tipo=EventType.RANGO_FECHAS)
        with self.assertRaises(ValidationError) as ctx:
            et.full_clean(exclude=['slug'])
        self.assertIn('rango_fecha_inicio', ctx.exception.message_dict)
        self.assertIn('rango_fecha_fin', ctx.exception.message_dict)

    def test_la_fecha_final_no_puede_ir_antes_que_la_inicial(self):
        et = _et(
            self.host, rango_tipo=EventType.RANGO_FECHAS,
            rango_fecha_inicio=date(2026, 5, 10),
            rango_fecha_fin=date(2026, 5, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            et.full_clean(exclude=['slug'])
        self.assertIn('rango_fecha_fin', ctx.exception.message_dict)

    def test_el_modo_rolling_no_exige_fechas(self):
        et = _et(self.host)
        et.full_clean(exclude=['slug'])  # no lanza


class RangoFechasFormularioTest(TestCase):
    """El panel manda un checkbox; el modelo guarda el modo como texto."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='rango.admin@test.com', username='rango_admin',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.et = _et(self.admin, nombre='Evento panel rango')
        self.url = reverse('panel_event_types:event_type_update', args=[self.et.pk])

    def _payload(self, **extra):
        datos = {
            'nombre': self.et.nombre,
            'descripcion': '',
            'duracion_minutos': 30,
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
        return datos

    def _post(self, **extra):
        c = Client()
        c.force_login(self.admin)
        return c.post(self.url, self._payload(**extra))

    def test_marcar_el_check_guarda_el_rango(self):
        self._post(
            rango_por_fechas='on',
            rango_fecha_inicio='2026-06-01',
            rango_fecha_fin='2026-06-30',
        )
        self.et.refresh_from_db()
        self.assertEqual(self.et.rango_tipo, EventType.RANGO_FECHAS)
        self.assertEqual(self.et.rango_fecha_inicio, date(2026, 6, 1))
        self.assertEqual(self.et.rango_fecha_fin, date(2026, 6, 30))

    def test_sin_el_check_se_queda_en_rolling(self):
        self._post()
        self.et.refresh_from_db()
        self.assertEqual(self.et.rango_tipo, EventType.RANGO_ROLLING)

    def test_marcar_el_check_sin_fechas_es_un_error_de_formulario(self):
        resp = self._post(rango_por_fechas='on')
        self.assertEqual(resp.status_code, 200)  # se re-renderiza con errores
        self.et.refresh_from_db()
        self.assertEqual(self.et.rango_tipo, EventType.RANGO_ROLLING)

    def test_la_fecha_final_anterior_a_la_inicial_es_un_error(self):
        resp = self._post(
            rango_por_fechas='on',
            rango_fecha_inicio='2026-06-30',
            rango_fecha_fin='2026-06-01',
        )
        self.assertEqual(resp.status_code, 200)
        self.et.refresh_from_db()
        self.assertEqual(self.et.rango_tipo, EventType.RANGO_ROLLING)

    def test_al_volver_con_errores_no_se_pierde_lo_escrito(self):
        # El formulario se re-renderiza con el string crudo del POST, no con un
        # date: si el template no lo formatea bien, los dos campos vuelven vacíos.
        resp = self._post(
            rango_por_fechas='on',
            rango_fecha_inicio='2026-06-30',
            rango_fecha_fin='2026-06-01',
        )
        html = resp.content.decode()
        self.assertIn('value="2026-06-30"', html)
        self.assertIn('value="2026-06-01"', html)
        self.assertIn('id="rango_por_fechas"', html)

    def test_un_fallo_de_cache_no_tumba_el_guardado(self):
        # La invalidación corre en on_commit, con el evento ya escrito: si revienta,
        # el usuario vería un 500 sobre algo que en realidad se guardó bien.
        with patch('calendario.bookings.services.invalidar_slots',
                   side_effect=Exception('cache caída')):
            resp = self._post(
                rango_por_fechas='on',
                rango_fecha_inicio='2026-06-01',
                rango_fecha_fin='2026-06-30',
            )
        self.assertEqual(resp.status_code, 302)
        self.et.refresh_from_db()
        self.assertEqual(self.et.rango_tipo, EventType.RANGO_FECHAS)

    def test_desmarcar_vuelve_al_rolling_conservando_las_fechas(self):
        # Las fechas se quedan guardadas sin efecto: volver a marcar el check no
        # obliga a escribirlas otra vez.
        self._post(
            rango_por_fechas='on',
            rango_fecha_inicio='2026-06-01',
            rango_fecha_fin='2026-06-30',
        )
        self._post(rango_fecha_inicio='2026-06-01', rango_fecha_fin='2026-06-30')
        self.et.refresh_from_db()
        self.assertEqual(self.et.rango_tipo, EventType.RANGO_ROLLING)
        self.assertEqual(self.et.rango_fecha_inicio, date(2026, 6, 1))
        self.assertFalse(self.et.usa_rango_de_fechas)
