"""
Tests del panel de disponibilidad para admins y supervisores.

Cubren el selector "Editar disponibilidad de tu grupo": permite gestionar la
disponibilidad y la zona horaria de otro usuario sin suplantarlo (magic login).

- Alcance: admin → todos; supervisor → su grupo; host normal → solo él mismo.
- Escrituras (`host=<pk>`) aplican al host elegido, no al que edita.
- Un host fuera del alcance devuelve 403.
"""
from datetime import time, timedelta

from django.contrib.messages import get_messages
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from calendario.availability.models import BloqueHorarioSemanal, BloqueHorarioFecha
from calendario.grupos.models import Grupo, GrupoXUsuario
from calendario.permisos.models import Rol, RolXUsuario
from tests.factories import crear_host, horario_default


def _reset_semanal(host):
    """Borra la disponibilidad semanal por defecto (sembrada por el signal)."""
    BloqueHorarioSemanal.objects.filter(horario__host=host).delete()


def _hacer_admin(user):
    rol, _ = Rol.objects.get_or_create(nombre='admin', defaults={'descripcion': 'Admin'})
    # El rol admin necesita los permisos de availability para pasar el mixin.
    from calendario.permisos.models import Permiso, PermisoXRol
    for codename in ('availability.ver', 'availability.editar'):
        permiso, _ = Permiso.objects.get_or_create(
            codename=codename, defaults={'nombre': codename}
        )
        PermisoXRol.objects.get_or_create(rol=rol, permiso=permiso)
    RolXUsuario.objects.get_or_create(usuario=user, rol=rol)
    return user


class DisponibilidadDeGrupoTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.supervisor = crear_host(email='supervisor@test.com', first_name='Sara')
        self.miembro = crear_host(email='miembro@test.com', first_name='Marco')
        self.ajeno = crear_host(email='ajeno@test.com', first_name='Ana')

        self.grupo = Grupo.objects.create(nombre='Ventas')
        GrupoXUsuario.objects.create(
            grupo=self.grupo, usuario=self.supervisor, es_supervisor=True
        )
        GrupoXUsuario.objects.create(grupo=self.grupo, usuario=self.miembro)

        otro_grupo = Grupo.objects.create(nombre='Soporte')
        GrupoXUsuario.objects.create(grupo=otro_grupo, usuario=self.ajeno)

        self.list_url = reverse('panel_disponibilidad:bloque_list')
        self.client.force_login(self.supervisor)

    # ── Selector ──

    def test_supervisor_ve_el_selector_con_su_grupo(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Editar horario de:')
        editables = {h['pk'] for h in resp.context['hosts_editables_json']}
        self.assertEqual(editables, {self.supervisor.pk, self.miembro.pk})

    def test_el_selector_lleva_nombre_email_e_iniciales(self):
        resp = self.client.get(self.list_url)
        marco = next(
            h for h in resp.context['hosts_editables_json'] if h['pk'] == self.miembro.pk
        )
        self.assertEqual(marco['nombre'], 'Marco Tovar')
        self.assertEqual(marco['email'], 'miembro@test.com')
        self.assertEqual(marco['iniciales'], 'MT')
        self.assertFalse(marco['es_yo'])

    def test_host_normal_no_ve_el_selector(self):
        self.client.force_login(self.miembro)
        resp = self.client.get(self.list_url)
        self.assertFalse(resp.context['puede_elegir_host'])
        self.assertNotContains(resp, 'Editar horario de:')

    def test_admin_ve_a_todos_los_usuarios_activos(self):
        admin = _hacer_admin(crear_host(email='admin.panel@test.com', first_name='Alba'))
        self.client.force_login(admin)
        resp = self.client.get(self.list_url)
        editables = {h['pk'] for h in resp.context['hosts_editables_json']}
        for user in (admin, self.supervisor, self.miembro, self.ajeno):
            self.assertIn(user.pk, editables)

    # ── Lectura ──

    def test_selecciona_miembro_y_carga_su_horario(self):
        _reset_semanal(self.supervisor)
        _reset_semanal(self.miembro)
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.miembro), dia_semana=2, hora_inicio=time(7, 0), hora_fin=time(11, 0),
        )
        resp = self.client.get(self.list_url, {'host': self.miembro.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['host_objetivo'], self.miembro)
        self.assertTrue(resp.context['editando_a_otro'])
        self.assertEqual(resp.context['horas_semanales_json'][2], [['07:00', '11:00']])

    def test_muestra_la_zona_horaria_del_host_seleccionado(self):
        self.miembro.timezone = 'America/Bogota'
        self.miembro.save(update_fields=['timezone'])
        resp = self.client.get(self.list_url, {'host': self.miembro.pk})
        self.assertContains(resp, 'America/Bogota')

    def test_host_fuera_del_grupo_devuelve_403(self):
        resp = self.client.get(self.list_url, {'host': self.ajeno.pk})
        self.assertEqual(resp.status_code, 403)

    def test_host_normal_no_puede_espiar_a_otro(self):
        self.client.force_login(self.miembro)
        resp = self.client.get(self.list_url, {'host': self.supervisor.pk})
        self.assertEqual(resp.status_code, 403)

    def test_host_inexistente_devuelve_403(self):
        resp = self.client.get(self.list_url, {'host': 999999})
        self.assertEqual(resp.status_code, 403)

    # ── Escritura ──

    def test_crea_bloque_semanal_al_miembro(self):
        _reset_semanal(self.miembro)
        _reset_semanal(self.supervisor)
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_create'),
            {'host': self.miembro.pk, 'dia_semana': 1,
             'hora_inicio': '10:00', 'hora_fin': '13:00'},
        )
        self.assertRedirects(resp, f'{self.list_url}?host={self.miembro.pk}')
        self.assertEqual(BloqueHorarioSemanal.objects.filter(horario__host=self.miembro).count(), 1)
        self.assertEqual(BloqueHorarioSemanal.objects.filter(horario__host=self.supervisor).count(), 0)

    def test_elimina_bloque_del_miembro(self):
        bloque = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.miembro), dia_semana=5, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_delete', args=[bloque.pk]),
            {'host': self.miembro.pk},
        )
        self.assertRedirects(resp, f'{self.list_url}?host={self.miembro.pk}')
        self.assertFalse(BloqueHorarioSemanal.objects.filter(pk=bloque.pk).exists())

    def test_no_elimina_bloque_de_un_host_fuera_de_alcance(self):
        bloque = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.ajeno), dia_semana=5, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_delete', args=[bloque.pk]),
            {'host': self.ajeno.pk},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(BloqueHorarioSemanal.objects.filter(pk=bloque.pk).exists())

    def test_limpiar_dia_del_miembro(self):
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.miembro), dia_semana=3, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.supervisor), dia_semana=3, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:dia_limpiar', args=[3]),
            {'host': self.miembro.pk},
        )
        self.assertRedirects(resp, f'{self.list_url}?host={self.miembro.pk}')
        self.assertFalse(
            BloqueHorarioSemanal.objects.filter(horario__host=self.miembro, dia_semana=3).exists()
        )
        self.assertTrue(
            BloqueHorarioSemanal.objects.filter(horario__host=self.supervisor, dia_semana=3).exists()
        )

    def test_horas_especificas_por_fecha_del_miembro(self):
        manana = timezone.localdate() + timedelta(days=1)
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_fecha_create'),
            {'host': self.miembro.pk, 'fechas': manana.isoformat(),
             'hora_inicio': ['08:00'], 'hora_fin': ['12:00']},
        )
        self.assertRedirects(resp, f'{self.list_url}?host={self.miembro.pk}')
        self.assertTrue(
            BloqueHorarioFecha.objects.filter(horario__host=self.miembro, fecha=manana).exists()
        )
        self.assertFalse(BloqueHorarioFecha.objects.filter(horario__host=self.supervisor).exists())

    def test_bloqueo_del_grupo_no_frena_al_supervisor(self):
        """bloquear_editar_disponibilidad afecta al host sobre su propio horario,
        no al supervisor que se lo edita desde el panel."""
        self.grupo.bloquear_editar_disponibilidad = True
        self.grupo.save(update_fields=['bloquear_editar_disponibilidad'])
        _reset_semanal(self.miembro)
        self.client.post(
            reverse('panel_disponibilidad:bloque_create'),
            {'host': self.miembro.pk, 'dia_semana': 6,
             'hora_inicio': '10:00', 'hora_fin': '13:00'},
        )
        self.assertEqual(
            BloqueHorarioSemanal.objects.filter(horario__host=self.miembro, dia_semana=6).count(), 1
        )

    # ── Zona horaria ──

    def test_supervisor_cambia_la_zona_horaria_del_miembro(self):
        resp = self.client.post(
            reverse('panel_usuarios:actualizar_timezone'),
            {'host': self.miembro.pk, 'timezone': 'America/Bogota',
             'next': f'{self.list_url}?host={self.miembro.pk}'},
        )
        self.assertEqual(resp.status_code, 302)
        self.miembro.refresh_from_db()
        self.supervisor.refresh_from_db()
        self.assertEqual(self.miembro.timezone, 'America/Bogota')
        self.assertEqual(self.supervisor.timezone, 'Europe/Madrid')

    def test_no_cambia_la_zona_horaria_de_un_host_fuera_de_alcance(self):
        resp = self.client.post(
            reverse('panel_usuarios:actualizar_timezone'),
            {'host': self.ajeno.pk, 'timezone': 'America/Bogota'},
        )
        self.assertEqual(resp.status_code, 403)
        self.ajeno.refresh_from_db()
        self.assertEqual(self.ajeno.timezone, 'Europe/Madrid')


class EdicionEnLineaTest(TestCase):
    """Cambiar las horas de un bloque existente sin borrarlo y volver a crearlo."""

    def setUp(self):
        self.client = Client()
        self.host = crear_host(email='edicion@test.com')
        self.client.force_login(self.host)
        _reset_semanal(self.host)
        self.bloque = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(13, 0),
        )
        self.list_url = reverse('panel_disponibilidad:bloque_list')

    def _editar(self, pk, inicio, fin):
        return self.client.post(
            reverse('panel_disponibilidad:bloque_update', args=[pk]),
            {'hora_inicio': inicio, 'hora_fin': fin},
        )

    def test_la_fila_del_bloque_es_un_formulario_editable(self):
        resp = self.client.get(self.list_url)
        self.assertContains(
            resp, reverse('panel_disponibilidad:bloque_update', args=[self.bloque.pk])
        )
        self.assertContains(resp, 'avail-time-editable')

    def test_cambia_las_horas_del_bloque(self):
        resp = self._editar(self.bloque.pk, '10:30', '14:00')
        self.assertRedirects(resp, self.list_url)
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.hora_inicio, time(10, 30))
        self.assertEqual(self.bloque.hora_fin, time(14, 0))

    def test_ampliar_un_bloque_no_exige_borrar_el_otro(self):
        """El caso que molestaba: estirar el primer bloque hasta pegarlo al segundo."""
        segundo = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=0, hora_inicio=time(16, 0), hora_fin=time(18, 0),
        )
        resp = self._editar(self.bloque.pk, '09:00', '16:00')
        self.assertRedirects(resp, self.list_url)
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.hora_fin, time(16, 0))
        self.assertTrue(BloqueHorarioSemanal.objects.filter(pk=segundo.pk).exists())

    def test_solape_con_otro_bloque_no_guarda_y_avisa(self):
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=0, hora_inicio=time(16, 0), hora_fin=time(18, 0),
        )
        resp = self._editar(self.bloque.pk, '09:00', '17:00')
        self.assertEqual(resp.status_code, 302)
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.hora_fin, time(13, 0))
        mensajes = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any('solapa' in m for m in mensajes), mensajes)

    def test_hora_fin_anterior_al_inicio_no_guarda(self):
        resp = self._editar(self.bloque.pk, '15:00', '11:00')
        self.assertRedirects(resp, self.list_url)
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.hora_inicio, time(9, 0))

    def test_horas_vacias_no_guardan(self):
        resp = self._editar(self.bloque.pk, '', '')
        self.assertRedirects(resp, self.list_url)
        self.bloque.refresh_from_db()
        self.assertEqual(self.bloque.hora_inicio, time(9, 0))

    def test_no_edita_el_bloque_de_otro_host(self):
        ajeno = crear_host(email='ajeno.edicion@test.com')
        bloque_ajeno = BloqueHorarioSemanal.objects.create(
            horario=horario_default(ajeno), dia_semana=1, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self._editar(bloque_ajeno.pk, '11:00', '12:00')
        self.assertEqual(resp.status_code, 404)
        bloque_ajeno.refresh_from_db()
        self.assertEqual(bloque_ajeno.hora_inicio, time(9, 0))

    def test_edita_un_horario_de_fecha_concreta(self):
        manana = timezone.localdate() + timedelta(days=1)
        bloque = BloqueHorarioFecha.objects.create(
            horario=horario_default(self.host), fecha=manana, hora_inicio=time(8, 0), hora_fin=time(12, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_fecha_update', args=[bloque.pk]),
            {'hora_inicio': '09:15', 'hora_fin': '13:45'},
        )
        self.assertRedirects(resp, self.list_url)
        bloque.refresh_from_db()
        self.assertEqual(bloque.hora_inicio, time(9, 15))
        self.assertEqual(bloque.hora_fin, time(13, 45))


class EdicionEnLineaDeGrupoTest(TestCase):
    """La edición en línea respeta el alcance del selector de host."""

    def setUp(self):
        self.client = Client()
        self.supervisor = crear_host(email='sup.inline@test.com')
        self.miembro = crear_host(email='miembro.inline@test.com')
        self.ajeno = crear_host(email='ajeno.inline@test.com')
        grupo = Grupo.objects.create(nombre='Inline')
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.supervisor, es_supervisor=True)
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.miembro)
        self.client.force_login(self.supervisor)
        self.list_url = reverse('panel_disponibilidad:bloque_list')
        _reset_semanal(self.miembro)
        _reset_semanal(self.ajeno)

    def test_supervisor_edita_el_bloque_del_miembro(self):
        bloque = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.miembro), dia_semana=2, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_update', args=[bloque.pk]),
            {'host': self.miembro.pk, 'hora_inicio': '11:00', 'hora_fin': '12:30'},
        )
        self.assertRedirects(resp, f'{self.list_url}?host={self.miembro.pk}')
        bloque.refresh_from_db()
        self.assertEqual(bloque.hora_inicio, time(11, 0))

    def test_no_edita_el_bloque_de_alguien_fuera_del_grupo(self):
        bloque = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.ajeno), dia_semana=2, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_update', args=[bloque.pk]),
            {'host': self.ajeno.pk, 'hora_inicio': '11:00', 'hora_fin': '12:30'},
        )
        self.assertEqual(resp.status_code, 403)
        bloque.refresh_from_db()
        self.assertEqual(bloque.hora_inicio, time(9, 0))


class CopiarHorasADiasTest(TestCase):
    """Icono de copiar del día: replica su horario completo en los días marcados.

    Calcado de Calendly (verificado contra la implementación de Cal.com): se
    copian todos los rangos del día y se reemplaza lo que hubiera en el destino.
    """

    def setUp(self):
        self.client = Client()
        self.host = crear_host(email='copiar@test.com')
        self.client.force_login(self.host)
        _reset_semanal(self.host)
        self.lunes = BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(17, 0),
        )
        self.list_url = reverse('panel_disponibilidad:bloque_list')

    def _copiar(self, dias, dia_origen=0, extra=None):
        datos = {'dias': dias}
        if extra:
            datos.update(extra)
        return self.client.post(
            reverse('panel_disponibilidad:dia_copiar', args=[dia_origen]), datos
        )

    def _rangos(self, dia):
        return [
            (b.hora_inicio, b.hora_fin)
            for b in BloqueHorarioSemanal.objects.filter(
                horario__host=self.host, dia_semana=dia
            ).order_by('hora_inicio')
        ]

    def test_el_popover_lista_los_siete_dias_y_seleccionar_todo(self):
        resp = self.client.get(self.list_url)
        self.assertContains(resp, 'Copiar horas a…')
        self.assertContains(resp, 'Seleccionar todo')
        self.assertContains(resp, reverse('panel_disponibilidad:dia_copiar', args=[0]))
        for etiqueta in ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'):
            self.assertContains(resp, etiqueta)

    def test_solo_la_primera_fila_del_dia_lleva_el_icono_de_copiar(self):
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=0, hora_inicio=time(19, 0), hora_fin=time(21, 0),
        )
        resp = self.client.get(self.list_url)
        # 'avail-btn-copy' también aparece en el CSS y el JS: cuenta el botón en sí
        self.assertEqual(resp.content.decode().count('data-pop="copy-dia-'), 1)

    def test_copia_el_horario_a_varios_dias(self):
        resp = self._copiar(['1', '2', '4'])
        self.assertRedirects(resp, self.list_url)
        for dia in (1, 2, 4):
            self.assertEqual(self._rangos(dia), [(time(9, 0), time(17, 0))])
        self.assertEqual(self._rangos(3), [])

    def test_copia_todos_los_rangos_del_dia_no_solo_uno(self):
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=0, hora_inicio=time(19, 0), hora_fin=time(21, 0),
        )
        self._copiar(['2'])
        self.assertEqual(
            self._rangos(2), [(time(9, 0), time(17, 0)), (time(19, 0), time(21, 0))]
        )

    def test_reemplaza_por_completo_el_dia_destino(self):
        """El destino queda idéntico al origen: lo que tenía desaparece."""
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=1, hora_inicio=time(7, 0), hora_fin=time(8, 0),
        )
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(self.host), dia_semana=1, hora_inicio=time(19, 0), hora_fin=time(21, 0),
        )
        self._copiar(['1'])
        self.assertEqual(self._rangos(1), [(time(9, 0), time(17, 0))])

    def test_el_dia_de_origen_no_se_toca(self):
        resp = self._copiar(['0'])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._rangos(0), [(time(9, 0), time(17, 0))])
        mensajes = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any('Selecciona al menos un día' in m for m in mensajes), mensajes)

    def test_copiar_dos_veces_deja_el_mismo_resultado(self):
        self._copiar(['1'])
        self._copiar(['1'])
        self.assertEqual(self._rangos(1), [(time(9, 0), time(17, 0))])

    def test_sin_dias_marcados_avisa(self):
        resp = self._copiar([])
        self.assertEqual(resp.status_code, 302)
        mensajes = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any('Selecciona al menos un día' in m for m in mensajes), mensajes)

    def test_valores_de_dia_invalidos_se_descartan(self):
        resp = self._copiar(['99', 'lunes', '-1'])
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioSemanal.objects.filter(horario__host=self.host).count(), 1)

    def test_copiar_desde_un_dia_vacio_avisa(self):
        resp = self._copiar(['1'], dia_origen=6)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._rangos(1), [])
        mensajes = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any('no tiene horarios' in m for m in mensajes), mensajes)

    def test_dia_de_origen_fuera_de_rango_da_404(self):
        resp = self._copiar(['1'], dia_origen=9)
        self.assertEqual(resp.status_code, 404)

    def test_copia_solo_dentro_del_calendario_del_host(self):
        ajeno = crear_host(email='ajeno.copiar@test.com')
        _reset_semanal(ajeno)
        self._copiar(['1'])
        self.assertEqual(
            BloqueHorarioSemanal.objects.filter(horario__host=ajeno).count(), 0
        )

    def test_supervisor_copia_en_el_calendario_del_miembro(self):
        supervisor = crear_host(email='sup.copiar@test.com')
        grupo = Grupo.objects.create(nombre='Copias')
        GrupoXUsuario.objects.create(grupo=grupo, usuario=supervisor, es_supervisor=True)
        GrupoXUsuario.objects.create(grupo=grupo, usuario=self.host)
        self.client.force_login(supervisor)
        resp = self._copiar(['3'], extra={'host': self.host.pk})
        self.assertRedirects(resp, f'{self.list_url}?host={self.host.pk}')
        self.assertEqual(self._rangos(3), [(time(9, 0), time(17, 0))])

    def test_no_copia_en_el_calendario_de_alguien_fuera_de_alcance(self):
        otro = crear_host(email='fuera.copiar@test.com')
        _reset_semanal(otro)
        BloqueHorarioSemanal.objects.create(
            horario=horario_default(otro), dia_semana=0, hora_inicio=time(8, 0), hora_fin=time(9, 0),
        )
        resp = self._copiar(['1'], extra={'host': otro.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            BloqueHorarioSemanal.objects.filter(horario__host=otro, dia_semana=1).count(), 0
        )
