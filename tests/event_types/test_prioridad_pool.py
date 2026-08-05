"""
Tests del guardado de la prioridad round-robin desde el panel.

El modal de "Configurar prioridad" envía un campo `prioridad_<host_id>` por cada
organizador seleccionado. La vista los normaliza (0..3, cualquier otra cosa cae al
valor por defecto) y los persiste en EventTypeXHost sin recrear las filas que ya
existían, para no perder el orden de entrada al pool.

El 0 es un valor legítimo: deja al organizador fuera del reparto de ese evento.
"""
from django.test import TestCase, Client
from django.urls import reverse

from calendario.event_types.models import EventType, EventTypeXHost
from calendario.event_types.views import _puede_configurar_prioridad
from calendario.grupos.models import Grupo, GrupoXUsuario
from calendario.users.models import User
from tests.factories import crear_host


class PrioridadPoolViewTest(TestCase):

    def setUp(self):
        self.a = crear_host(email='pool.a@test.com', first_name='Ana', last_name='A')
        self.b = crear_host(email='pool.b@test.com', first_name='Beto', last_name='B')
        self.admin = User.objects.create_user(
            email='admin.prio@test.com', username='admin_prio',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.et = EventType.objects.create(
            host=self.a, nombre='Evento equipo prio', duracion_minutos=30,
            aviso_maximo_dias=60, incremento_inicio_minutos=30,
            slug_equipo='evento-equipo-prio', activo=True,
        )
        self.pivot_a = EventTypeXHost.objects.create(event_type=self.et, host=self.a)
        self.pivot_b = EventTypeXHost.objects.create(event_type=self.et, host=self.b)
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
            'es_equipo': 'on',
            'hosts': [str(self.a.pk), str(self.b.pk)],
        }
        datos.update(extra)
        return datos

    def _post(self, **extra):
        c = Client()
        c.force_login(self.admin)
        return c.post(self.url, self._payload(**extra))

    def _prioridades(self):
        return dict(
            EventTypeXHost.objects
            .filter(event_type=self.et)
            .values_list('host_id', 'prioridad')
        )

    def test_guarda_las_prioridades_enviadas(self):
        self._post(**{
            f'prioridad_{self.a.pk}': '1',
            f'prioridad_{self.b.pk}': '3',
        })
        self.assertEqual(self._prioridades(), {self.a.pk: 1, self.b.pk: 3})

    def test_sin_campos_de_prioridad_todos_quedan_por_defecto(self):
        # Un POST del formulario sin pasar por el modal no debe alterar nada.
        self._post()
        defecto = EventTypeXHost.PRIORIDAD_DEFECTO
        self.assertEqual(self._prioridades(), {self.a.pk: defecto, self.b.pk: defecto})

    def test_valores_invalidos_caen_al_valor_por_defecto(self):
        self._post(**{
            f'prioridad_{self.a.pk}': '99',
            f'prioridad_{self.b.pk}': 'abc',
        })
        defecto = EventTypeXHost.PRIORIDAD_DEFECTO
        self.assertEqual(self._prioridades(), {self.a.pk: defecto, self.b.pk: defecto})

    def test_el_cero_se_guarda_como_exclusion(self):
        self._post(**{
            f'prioridad_{self.a.pk}': '0',
            f'prioridad_{self.b.pk}': '2',
        })
        self.assertEqual(self._prioridades(), {self.a.pk: 0, self.b.pk: 2})
        pivot = EventTypeXHost.objects.get(event_type=self.et, host=self.a)
        self.assertTrue(pivot.excluido)

    def test_los_negativos_no_son_una_exclusion(self):
        # -1 no es "más excluido": es basura y cae al valor por defecto.
        self._post(**{f'prioridad_{self.a.pk}': '-1'})
        self.assertEqual(
            self._prioridades()[self.a.pk], EventTypeXHost.PRIORIDAD_DEFECTO,
        )

    def test_el_excluido_sigue_en_el_pool(self):
        # Poner 0 no es quitarlo: la fila (y con ella el orden de entrada) se queda.
        self._post(**{f'prioridad_{self.a.pk}': '0', f'prioridad_{self.b.pk}': '1'})
        pivot = EventTypeXHost.objects.get(event_type=self.et, host=self.a)
        self.assertEqual(pivot.pk, self.pivot_a.pk)

    def test_un_host_del_pool_no_puede_autoexcluirse(self):
        c = Client()
        c.force_login(self.b)
        c.post(self.url, self._payload(**{f'prioridad_{self.b.pk}': '0'}))
        self.assertEqual(
            self._prioridades()[self.b.pk], EventTypeXHost.PRIORIDAD_DEFECTO,
        )

    def test_no_recrea_las_filas_existentes(self):
        # El orden de entrada al pool (pivot.id) es el último desempate del
        # round-robin: cambiar prioridades no debe reiniciarlo.
        self._post(**{
            f'prioridad_{self.a.pk}': '2',
            f'prioridad_{self.b.pk}': '3',
        })
        ids = dict(
            EventTypeXHost.objects
            .filter(event_type=self.et)
            .values_list('host_id', 'id')
        )
        self.assertEqual(ids, {self.a.pk: self.pivot_a.pk, self.b.pk: self.pivot_b.pk})

    def test_un_host_del_pool_no_puede_cambiar_prioridades(self):
        # Beto solo está en el pool: no creó el evento ni supervisa a quien lo creó.
        EventTypeXHost.objects.filter(event_type=self.et, host=self.a).update(prioridad=3)
        c = Client()
        c.force_login(self.b)
        c.post(self.url, self._payload(**{
            f'prioridad_{self.a.pk}': '1',
            f'prioridad_{self.b.pk}': '3',
        }))
        # El POST trae los campos, pero se ignoran: nada se movió.
        self.assertEqual(
            self._prioridades(),
            {self.a.pk: 3, self.b.pk: EventTypeXHost.PRIORIDAD_DEFECTO},
        )

    def test_host_nuevo_entra_con_su_prioridad(self):
        c = crear_host(email='pool.c@test.com', first_name='Caro', last_name='C')
        self._post(
            hosts=[str(self.a.pk), str(self.b.pk), str(c.pk)],
            **{
                f'prioridad_{self.a.pk}': '1',
                f'prioridad_{self.b.pk}': '2',
                f'prioridad_{c.pk}': '3',
            },
        )
        self.assertEqual(
            self._prioridades(),
            {self.a.pk: 1, self.b.pk: 2, c.pk: 3},
        )


class PuedeConfigurarPrioridadTest(TestCase):
    """
    Quién ve el botón: admin general, creador del evento y supervisor del grupo
    del creador. El resto no, aunque esté en el pool del evento.
    """

    def setUp(self):
        self.creador = crear_host(email='vis.creador@test.com', first_name='Cre', last_name='Ador')
        self.et = EventType.objects.create(
            host=self.creador, nombre='Evento visibilidad', duracion_minutos=30,
            aviso_maximo_dias=60, incremento_inicio_minutos=30, activo=True,
        )

    def _usuario(self, email):
        return User.objects.create_user(
            email=email, username=email.split('@')[0],
            password='test1234', is_active=True,
        )

    def test_admin_general_ve_todo(self):
        admin = self._usuario('vis.admin@test.com')
        admin.is_superuser = True
        admin.save(update_fields=['is_superuser'])
        self.assertTrue(_puede_configurar_prioridad(admin, self.et))

    def test_el_creador_ve_su_evento(self):
        self.assertTrue(_puede_configurar_prioridad(self.creador, self.et))

    def test_el_supervisor_del_grupo_ve_el_evento_del_miembro(self):
        grupo = Grupo.objects.create(nombre='Docentes')
        supervisor = self._usuario('vis.super@test.com')
        GrupoXUsuario.objects.create(grupo=grupo, usuario=supervisor, es_supervisor=True)
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.creador, es_supervisor=False)
        self.assertTrue(_puede_configurar_prioridad(supervisor, self.et))

    def test_un_miembro_del_mismo_grupo_no_supervisor_no_ve(self):
        grupo = Grupo.objects.create(nombre='Docentes')
        companero = self._usuario('vis.compa@test.com')
        GrupoXUsuario.objects.create(grupo=grupo, usuario=companero, es_supervisor=False)
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.creador, es_supervisor=False)
        self.assertFalse(_puede_configurar_prioridad(companero, self.et))

    def test_un_host_del_pool_ajeno_no_ve(self):
        otro = self._usuario('vis.otro@test.com')
        EventTypeXHost.objects.create(event_type=self.et, host=otro)
        self.assertFalse(_puede_configurar_prioridad(otro, self.et))

    def test_supervisor_de_otro_grupo_no_ve(self):
        otro_grupo = Grupo.objects.create(nombre='Ventas')
        supervisor = self._usuario('vis.super2@test.com')
        GrupoXUsuario.objects.create(grupo=otro_grupo, usuario=supervisor, es_supervisor=True)
        self.assertFalse(_puede_configurar_prioridad(supervisor, self.et))

    def test_en_el_alta_siempre_puede(self):
        # Quien crea el evento es su creador por definición.
        cualquiera = self._usuario('vis.nuevo@test.com')
        self.assertTrue(_puede_configurar_prioridad(cualquiera, None))
