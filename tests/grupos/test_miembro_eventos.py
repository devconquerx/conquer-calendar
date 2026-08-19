"""
Alta y baja masiva de un miembro del grupo en varios tipos de evento.

La columna "Eventos" de /panel/grupos/ muestra en cuántos está cada miembro y
el botón "+" abre el modal donde se marcan/desmarcan de golpe.

Cubre: alcance de admin y supervisor, el conteo de la columna, el guardado
(altas, bajas y ambas a la vez), la protección del creador del evento y los
403 de quien no supervisa o no tiene permisos.
"""
import json

from django.test import TestCase, Client
from django.urls import reverse

from calendario.event_types.models import EventType, EventTypeXHost
from calendario.grupos.models import Grupo, GrupoXUsuario
from calendario.permisos.models import Permiso, PermisoXRol, Rol, RolXUsuario
from tests.factories import crear_host, crear_event_type


def _dar_permisos(user, *codenames):
    rol, _ = Rol.objects.get_or_create(
        nombre=f'rol-test-{user.pk}', defaults={'descripcion': 'test'}
    )
    for codename in codenames:
        permiso, _ = Permiso.objects.get_or_create(
            codename=codename, defaults={'nombre': codename}
        )
        PermisoXRol.objects.get_or_create(rol=rol, permiso=permiso)
    RolXUsuario.objects.get_or_create(usuario=user, rol=rol)
    return user


class MiembroEventosTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.supervisor = crear_host(email='sup.eventos@test.com', first_name='Sara')
        self.miembro = crear_host(email='miembro.eventos@test.com', first_name='Marco')
        self.ajeno = crear_host(email='ajeno.eventos@test.com', first_name='Ana')

        self.grupo = Grupo.objects.create(nombre='Ventas')
        GrupoXUsuario.objects.create(
            grupo=self.grupo, usuario=self.supervisor, es_supervisor=True
        )
        GrupoXUsuario.objects.create(grupo=self.grupo, usuario=self.miembro)

        _dar_permisos(self.supervisor, 'grupos.ver', 'event_types.editar')

        # Eventos del grupo (creados por el miembro y por el supervisor).
        self.ev_miembro = crear_event_type(self.miembro, nombre='Clase de Marco')
        self.ev_sup = crear_event_type(self.supervisor, nombre='Demo de Sara')
        self.ev_sup2 = crear_event_type(self.supervisor, nombre='Onboarding')
        # Evento de fuera del grupo.
        self.ev_ajeno = crear_event_type(self.ajeno, nombre='Sesión de Ana')

        self.url = reverse(
            'panel_grupos:miembro_eventos', args=[self.grupo.pk, self.miembro.pk]
        )
        self.client.force_login(self.supervisor)

    # ── GET: lista de eventos ──

    def test_lista_los_eventos_del_alcance_con_su_estado(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        datos = resp.json()
        self.assertEqual(datos['miembro'], 'Marco Tovar')

        por_nombre = {e['nombre']: e for e in datos['eventos']}
        self.assertIn('Clase de Marco', por_nombre)
        self.assertIn('Demo de Sara', por_nombre)
        self.assertNotIn('Sesión de Ana', por_nombre)

        self.assertTrue(por_nombre['Clase de Marco']['asignado'])
        self.assertTrue(por_nombre['Clase de Marco']['es_creador'])
        self.assertFalse(por_nombre['Demo de Sara']['asignado'])

    def test_marca_los_eventos_en_los_que_ya_participa(self):
        EventTypeXHost.objects.create(event_type=self.ev_sup, host=self.miembro)
        datos = self.client.get(self.url).json()
        por_nombre = {e['nombre']: e for e in datos['eventos']}
        self.assertTrue(por_nombre['Demo de Sara']['asignado'])
        self.assertFalse(por_nombre['Demo de Sara']['es_creador'])
        self.assertEqual(datos['total_asignados'], 2)

    def test_un_admin_ve_todos_los_eventos(self):
        admin = crear_host(email='admin.eventos@test.com')
        Rol.objects.get_or_create(nombre='admin', defaults={'descripcion': 'admin'})
        RolXUsuario.objects.create(usuario=admin, rol=Rol.objects.get(nombre='admin'))
        _dar_permisos(admin, 'grupos.ver', 'event_types.editar')
        self.client.force_login(admin)
        nombres = {e['nombre'] for e in self.client.get(self.url).json()['eventos']}
        self.assertIn('Sesión de Ana', nombres)

    # ── POST: guardar ──

    def test_anade_al_miembro_a_varios_eventos_de_golpe(self):
        resp = self.client.post(
            self.url, {'eventos': [self.ev_miembro.pk, self.ev_sup.pk, self.ev_sup2.pk]}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['anadidos'], 2)
        self.assertEqual(resp.json()['total'], 3)
        self.assertTrue(
            EventTypeXHost.objects.filter(event_type=self.ev_sup, host=self.miembro).exists()
        )

    def test_quita_al_miembro_de_los_eventos_desmarcados(self):
        EventTypeXHost.objects.create(event_type=self.ev_sup, host=self.miembro)
        EventTypeXHost.objects.create(event_type=self.ev_sup2, host=self.miembro)
        resp = self.client.post(self.url, {'eventos': [self.ev_miembro.pk, self.ev_sup.pk]})
        self.assertEqual(resp.json()['quitados'], 1)
        self.assertFalse(
            EventTypeXHost.objects.filter(event_type=self.ev_sup2, host=self.miembro).exists()
        )
        self.assertTrue(
            EventTypeXHost.objects.filter(event_type=self.ev_sup, host=self.miembro).exists()
        )

    def test_alta_y_baja_en_la_misma_operacion(self):
        EventTypeXHost.objects.create(event_type=self.ev_sup, host=self.miembro)
        resp = self.client.post(self.url, {'eventos': [self.ev_miembro.pk, self.ev_sup2.pk]})
        datos = resp.json()
        self.assertEqual((datos['anadidos'], datos['quitados']), (1, 1))

    def test_nace_con_la_prioridad_por_defecto(self):
        self.client.post(self.url, {'eventos': [self.ev_sup.pk]})
        pivot = EventTypeXHost.objects.get(event_type=self.ev_sup, host=self.miembro)
        self.assertEqual(pivot.prioridad, EventTypeXHost.PRIORIDAD_DEFECTO)

    def test_no_saca_al_creador_de_su_propio_evento(self):
        """Dejaría el evento sin organizador: el check va bloqueado y el POST lo ignora."""
        resp = self.client.post(self.url, {'eventos': []})
        self.assertEqual(resp.json()['quitados'], 0)
        self.assertTrue(
            EventTypeXHost.objects.filter(event_type=self.ev_miembro, host=self.miembro).exists()
        )

    def test_no_toca_los_eventos_fuera_del_alcance(self):
        EventTypeXHost.objects.create(event_type=self.ev_ajeno, host=self.miembro)
        self.client.post(self.url, {'eventos': [self.ev_miembro.pk]})
        self.assertTrue(
            EventTypeXHost.objects.filter(event_type=self.ev_ajeno, host=self.miembro).exists()
        )

    def test_ids_invalidos_se_descartan(self):
        resp = self.client.post(self.url, {'eventos': ['abc', '999999', '']})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['anadidos'], 0)

    # ── Permisos ──

    def test_quien_no_supervisa_el_grupo_recibe_403(self):
        otro = crear_host(email='otro.sup@test.com')
        _dar_permisos(otro, 'grupos.ver', 'event_types.editar')
        self.client.force_login(otro)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'eventos': []}).status_code, 403)

    def test_sin_permiso_de_event_types_recibe_403(self):
        sin_permiso = crear_host(email='sin.permiso@test.com')
        GrupoXUsuario.objects.create(
            grupo=self.grupo, usuario=sin_permiso, es_supervisor=True
        )
        Permiso.objects.filter(codename='event_types.editar').delete()
        self.client.force_login(sin_permiso)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_usuario_que_no_es_del_grupo_da_404(self):
        url = reverse('panel_grupos:miembro_eventos', args=[self.grupo.pk, self.ajeno.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonimo_es_redirigido(self):
        resp = Client().get(self.url)
        self.assertEqual(resp.status_code, 302)


class ColumnaEventosEnListadoTest(TestCase):
    """La tabla de miembros muestra el número de eventos y el botón de editar."""

    def setUp(self):
        self.client = Client()
        self.supervisor = crear_host(email='sup.col@test.com')
        self.miembro = crear_host(email='miembro.col@test.com')
        grupo = Grupo.objects.create(nombre='Soporte')
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.supervisor, es_supervisor=True)
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.miembro)
        _dar_permisos(self.supervisor, 'grupos.ver', 'event_types.editar')
        self.grupo = grupo
        self.client.force_login(self.supervisor)

    def test_muestra_la_columna_y_el_conteo(self):
        crear_event_type(self.miembro, nombre='Uno')
        otro = crear_event_type(self.supervisor, nombre='Dos')
        EventTypeXHost.objects.create(event_type=otro, host=self.miembro)

        resp = self.client.get(reverse('panel_grupos:grupo_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Eventos')
        self.assertContains(
            resp,
            f'id="conteo-eventos-{self.grupo.pk}-{self.miembro.pk}"',
        )
        miembros = {
            m.usuario.pk: m.usuario.num_eventos
            for g in resp.context['grupos'] for m in g.membresias.all()
        }
        self.assertEqual(miembros[self.miembro.pk], 2)
        self.assertEqual(miembros[self.supervisor.pk], 1)

    def test_sin_permiso_de_event_types_no_sale_el_boton(self):
        Permiso.objects.filter(codename='event_types.editar').delete()
        resp = self.client.get(reverse('panel_grupos:grupo_list'))
        self.assertFalse(resp.context['puede_editar_eventos'])
        self.assertNotContains(resp, 'btn-eventos')
