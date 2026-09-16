"""
Buscador del listado de tipos de evento: por nombre (un trozo) o por ID (el
número exacto).
"""
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from calendario.users.models import User
from tests.factories import crear_event_type, crear_host

PATCH_SYNC = 'calendario.google_calendar.sync.sincronizar_host_completo'


@patch(PATCH_SYNC)
class BuscarTiposDeEventoTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.buscar.listado@test.com')
        self.admin = User.objects.create_user(
            email='admin.buscar.listado@test.com', username='admin_buscar_listado',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.url = reverse('panel_event_types:event_type_list')
        self.uno = crear_event_type(self.host, nombre='Llamada Finance', duracion=30)
        self.otro = crear_event_type(self.host, nombre='Otra llamada', duracion=30)
        # Un nombre con el número del ID del primero: por ID no debe salir.
        self.con_numero = crear_event_type(
            self.host, nombre=f'Clase {self.uno.pk}', duracion=30,
        )

    def _pks(self, **params):
        c = Client()
        c.force_login(self.admin)
        r = c.get(self.url, params)
        self.assertEqual(r.status_code, 200)
        return {et.pk for et in r.context['event_types']}

    def test_por_nombre_busca_un_trozo_del_nombre(self, _sync):
        self.assertEqual(self._pks(q='llamada'), {self.uno.pk, self.otro.pk})

    def test_por_nombre_un_numero_busca_en_el_nombre(self, _sync):
        self.assertIn(self.con_numero.pk, self._pks(q=str(self.uno.pk)))

    def test_por_id_trae_solo_ese_evento(self, _sync):
        self.assertEqual(self._pks(q=str(self.uno.pk), buscar_por='id'), {self.uno.pk})

    def test_por_id_acepta_la_almohadilla(self, _sync):
        self.assertEqual(self._pks(q=f'#{self.uno.pk}', buscar_por='id'), {self.uno.pk})

    def test_por_id_con_texto_no_trae_nada(self, _sync):
        self.assertEqual(self._pks(q='llamada', buscar_por='id'), set())

    def test_por_id_no_salta_la_visibilidad(self, _sync):
        # Un host que no participa en el evento no lo ve buscándolo por su ID.
        ajeno = crear_host(email='ajeno.buscar.listado@test.com')
        c = Client()
        c.force_login(ajeno)
        r = c.get(self.url, {'q': str(self.uno.pk), 'buscar_por': 'id'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['event_types']), [])

    def test_la_pantalla_recuerda_que_se_busca_por_id(self, _sync):
        c = Client()
        c.force_login(self.admin)
        html = c.get(self.url, {'q': str(self.uno.pk), 'buscar_por': 'id'}).content.decode()
        self.assertIn('<option value="id" selected>', html)
