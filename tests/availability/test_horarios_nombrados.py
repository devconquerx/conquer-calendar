"""
Tests de los horarios con nombre.

Sustituyen a los de `DisponibilidadEtxh`, que era la versión no reutilizable de
lo mismo. Cubre:

- Motor de slots: el horario asignado al tipo de evento manda; sin asignar, el
  default de la persona.
- Excepciones por fecha dentro del horario, incluido el día cerrado.
- Aislamiento: el horario de un evento no toca a los demás eventos del host.
- Modelo: un único default por persona, nombres únicos.
- CRUD de horarios y asignación a varios tipos de evento de una vez.
"""
from datetime import time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from calendario.availability.models import (
    BloqueHorarioFecha, BloqueHorarioSemanal, Horario,
)
from calendario.bookings.services import calcular_slots
from calendario.event_types.models import EventType, EventTypeXHost
from calendario.users.models import User
from tests.factories import crear_event_type, crear_host, horario_default

TZ = 'America/Bogota'
PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'
PATCH_SYNC = 'calendario.google_calendar.sync.sincronizar_host_completo'


def _horas_locales(slots, tz=TZ):
    return sorted({s.astimezone(ZoneInfo(tz)).hour for s in slots})


def _proximo_dia(dia_semana):
    hoy = timezone.localdate()
    dias = (dia_semana - hoy.weekday()) % 7 or 7
    return hoy + timedelta(days=dias)


def _host_en_tz(email):
    host = crear_host(email=email)
    host.timezone = TZ
    host.save(update_fields=['timezone'])
    # El signal deja un Default con lunes-viernes 00:00–23:59; se vacía para que
    # cada test declare exactamente las horas que quiere.
    BloqueHorarioSemanal.objects.filter(horario__host=host).delete()
    return host


def _franja(horario, dia, inicio, fin):
    return BloqueHorarioSemanal.objects.create(
        horario=horario, dia_semana=dia, hora_inicio=inicio, hora_fin=fin,
    )


def _fecha(horario, fecha, inicio=None, fin=None):
    return BloqueHorarioFecha.objects.create(
        horario=horario, fecha=fecha, hora_inicio=inicio, hora_fin=fin,
    )


# ---------------------------------------------------------------------------
# 1. Motor de slots — qué horario manda
# ---------------------------------------------------------------------------

@patch(PATCH_BUSY, return_value=[])
class ResolucionDeHorarioTest(TestCase):

    def setUp(self):
        self.host = _host_en_tz('host.horarios@test.com')
        self.default = horario_default(self.host)
        self.et = crear_event_type(self.host, nombre='Evento', duracion=60)
        self.etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.host)
        self.lunes = _proximo_dia(0)
        _franja(self.default, 0, time(9, 0), time(11, 0))

    def test_sin_horario_asignado_usa_el_default(self, _busy):
        self.assertIsNone(self.etxh.horario_id)
        slots = calcular_slots(self.et, self.lunes, self.lunes)
        self.assertEqual(_horas_locales(slots), [9, 10])

    def test_con_horario_asignado_ignora_el_default(self, _busy):
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(14, 0), time(16, 0))
        self.etxh.horario = usa
        self.etxh.save(update_fields=['horario'])

        slots = calcular_slots(self.et, self.lunes, self.lunes)
        self.assertEqual(_horas_locales(slots), [14, 15])

    def test_quitar_el_horario_devuelve_al_default(self, _busy):
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(14, 0), time(16, 0))
        self.etxh.horario = usa
        self.etxh.save(update_fields=['horario'])
        self.etxh.horario = None
        self.etxh.save(update_fields=['horario'])

        slots = calcular_slots(self.et, self.lunes, self.lunes)
        self.assertEqual(_horas_locales(slots), [9, 10])

    def test_borrar_el_horario_devuelve_al_default(self, _busy):
        # SET_NULL: quedarse sin horario es volver al default, no quedarse sin horas.
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(14, 0), time(16, 0))
        self.etxh.horario = usa
        self.etxh.save(update_fields=['horario'])
        usa.delete()

        self.etxh.refresh_from_db()
        self.assertIsNone(self.etxh.horario_id)
        self.assertEqual(_horas_locales(calcular_slots(self.et, self.lunes, self.lunes)), [9, 10])

    def test_un_horario_propio_no_toca_a_los_demas_eventos(self, _busy):
        otro_et = crear_event_type(self.host, nombre='Otro evento', duracion=60)
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(14, 0), time(16, 0))
        self.etxh.horario = usa
        self.etxh.save(update_fields=['horario'])

        self.assertEqual(_horas_locales(calcular_slots(self.et, self.lunes, self.lunes)), [14, 15])
        self.assertEqual(_horas_locales(calcular_slots(otro_et, self.lunes, self.lunes)), [9, 10])

    def test_un_horario_vale_para_varios_eventos_a_la_vez(self, _busy):
        # Justo lo que motivó la función: un horario, varios eventos.
        segundo = crear_event_type(self.host, nombre='Segundo', duracion=60)
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(14, 0), time(16, 0))
        EventTypeXHost.objects.filter(
            host=self.host, event_type__in=[self.et, segundo]
        ).update(horario=usa)

        for et in (self.et, segundo):
            self.assertEqual(_horas_locales(calcular_slots(et, self.lunes, self.lunes)), [14, 15])

    def test_cambiar_el_horario_cambia_los_dos_eventos_de_golpe(self, _busy):
        segundo = crear_event_type(self.host, nombre='Segundo', duracion=60)
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(14, 0), time(16, 0))
        EventTypeXHost.objects.filter(
            host=self.host, event_type__in=[self.et, segundo]
        ).update(horario=usa)

        BloqueHorarioSemanal.objects.filter(horario=usa).delete()
        _franja(usa, 0, time(18, 0), time(20, 0))

        for et in (self.et, segundo):
            self.assertEqual(_horas_locales(calcular_slots(et, self.lunes, self.lunes)), [18, 19])

    def test_host_sin_ningun_horario_no_ofrece_huecos(self, _busy):
        Horario.objects.filter(host=self.host).delete()
        self.assertEqual(calcular_slots(self.et, self.lunes, self.lunes), [])


# ---------------------------------------------------------------------------
# 2. Motor de slots — excepciones por fecha dentro del horario
# ---------------------------------------------------------------------------

@patch(PATCH_BUSY, return_value=[])
class ExcepcionesDeFechaTest(TestCase):

    def setUp(self):
        self.host = _host_en_tz('host.fechas.horarios@test.com')
        self.default = horario_default(self.host)
        self.et = crear_event_type(self.host, nombre='Evento fechas', duracion=60)
        self.lunes = _proximo_dia(0)
        _franja(self.default, 0, time(9, 0), time(11, 0))

    def test_la_fecha_reemplaza_la_franja_semanal(self, _busy):
        _fecha(self.default, self.lunes, time(14, 0), time(16, 0))
        self.assertEqual(_horas_locales(calcular_slots(self.et, self.lunes, self.lunes)), [14, 15])

    def test_varias_franjas_el_mismo_dia_se_suman(self, _busy):
        # Mañana y tarde partidas: antes cada fila pisaba a la anterior.
        _fecha(self.default, self.lunes, time(9, 0), time(11, 0))
        _fecha(self.default, self.lunes, time(15, 0), time(17, 0))
        self.assertEqual(
            _horas_locales(calcular_slots(self.et, self.lunes, self.lunes)),
            [9, 10, 15, 16],
        )

    def test_dia_cerrado_no_deja_huecos(self, _busy):
        _fecha(self.default, self.lunes, None, None)
        self.assertEqual(calcular_slots(self.et, self.lunes, self.lunes), [])

    def test_la_excepcion_solo_afecta_a_su_fecha(self, _busy):
        siguiente = self.lunes + timedelta(days=7)
        _fecha(self.default, self.lunes, time(14, 0), time(16, 0))
        slots = calcular_slots(self.et, self.lunes, siguiente)
        tz = ZoneInfo(TZ)
        horas = lambda d: sorted({s.astimezone(tz).hour for s in slots if s.astimezone(tz).date() == d})
        self.assertEqual(horas(self.lunes), [14, 15])
        self.assertEqual(horas(siguiente), [9, 10])

    def test_la_excepcion_abre_un_dia_sin_franja_semanal(self, _busy):
        martes = _proximo_dia(1)
        self.assertEqual(calcular_slots(self.et, martes, martes), [])
        _fecha(self.default, martes, time(10, 0), time(12, 0))
        self.assertEqual(_horas_locales(calcular_slots(self.et, martes, martes)), [10, 11])

    def test_la_excepcion_vive_dentro_de_su_horario(self, _busy):
        # Un festivo del Horario USA no tapa el día en el Default.
        usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        _franja(usa, 0, time(9, 0), time(11, 0))
        _fecha(usa, self.lunes, None, None)

        etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.host)
        self.assertEqual(_horas_locales(calcular_slots(self.et, self.lunes, self.lunes)), [9, 10])

        etxh.horario = usa
        etxh.save(update_fields=['horario'])
        self.assertEqual(calcular_slots(self.et, self.lunes, self.lunes), [])


# ---------------------------------------------------------------------------
# 3. Modelo
# ---------------------------------------------------------------------------

class HorarioModelTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.modelo.horarios@test.com')

    def test_el_usuario_nace_con_su_default(self):
        # Lo crea el signal: sin default no habría a dónde caer.
        defaults = Horario.objects.filter(host=self.host, es_default=True)
        self.assertEqual(defaults.count(), 1)
        self.assertEqual(defaults.first().nombre, Horario.NOMBRE_DEFAULT)

    def test_no_caben_dos_defaults(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Horario.objects.create(host=self.host, nombre='Otro', es_default=True)

    def test_no_caben_dos_nombres_iguales(self):
        Horario.objects.create(host=self.host, nombre='Horario USA')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Horario.objects.create(host=self.host, nombre='Horario USA')

    def test_dos_personas_pueden_usar_el_mismo_nombre(self):
        otro = crear_host(email='otro.modelo.horarios@test.com')
        Horario.objects.create(host=self.host, nombre='Horario USA')
        Horario.objects.create(host=otro, nombre='Horario USA')
        self.assertEqual(Horario.objects.filter(nombre='Horario USA').count(), 2)

    def test_borrar_el_horario_se_lleva_sus_bloques(self):
        h = Horario.objects.create(host=self.host, nombre='Temporal')
        _franja(h, 0, time(9, 0), time(10, 0))
        h.delete()
        self.assertEqual(BloqueHorarioSemanal.objects.filter(horario_id=h.pk).count(), 0)

    def test_el_dia_cerrado_se_lee_como_tal(self):
        h = horario_default(self.host)
        cerrado = _fecha(h, timezone.localdate() + timedelta(days=3))
        self.assertTrue(cerrado.cerrado)
        self.assertIn('cerrado', str(cerrado))


# ---------------------------------------------------------------------------
# 4. Panel — CRUD de horarios y asignación a eventos
# ---------------------------------------------------------------------------

@patch(PATCH_SYNC)
class PanelHorariosTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.panel.horarios@test.com')
        self.admin = User.objects.create_user(
            email='admin.horarios@test.com', username='admin_horarios',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.default = horario_default(self.host)
        self.et = crear_event_type(self.host, nombre='Evento panel', duracion=30)
        self.otro_et = crear_event_type(self.host, nombre='Otro panel', duracion=30)
        self.etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.host)
        self.otro_etxh = EventTypeXHost.objects.get(event_type=self.otro_et, host=self.host)

    def _cliente(self, quien=None):
        c = Client()
        c.force_login(quien or self.host)
        return c

    def _url(self, nombre, **kwargs):
        return reverse(f'panel_disponibilidad:{nombre}', kwargs=kwargs)

    # --- CRUD ---

    def test_crear_horario(self, _sync):
        self._cliente().post(self._url('horario_create'), {'nombre': 'Horario USA'})
        self.assertTrue(Horario.objects.filter(host=self.host, nombre='Horario USA').exists())

    def test_crear_con_nombre_repetido_no_choca(self, _sync):
        # En vez de un error de integridad, se le pone un sufijo.
        Horario.objects.create(host=self.host, nombre='Horario USA')
        self._cliente().post(self._url('horario_create'), {'nombre': 'Horario USA'})
        self.assertTrue(Horario.objects.filter(host=self.host, nombre='Horario USA (2)').exists())

    def test_renombrar_horario(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Provisional')
        self._cliente().post(self._url('horario_rename', pk=h.pk), {'nombre': 'Horario USA'})
        h.refresh_from_db()
        self.assertEqual(h.nombre, 'Horario USA')

    def test_duplicar_copia_franjas_y_fechas(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Origen')
        _franja(h, 0, time(9, 0), time(11, 0))
        _fecha(h, timezone.localdate() + timedelta(days=2), time(15, 0), time(16, 0))

        self._cliente().post(self._url('horario_duplicate', pk=h.pk))

        copia = Horario.objects.get(host=self.host, nombre='Origen (copia)')
        self.assertEqual(copia.bloques_semanales.count(), 1)
        self.assertEqual(copia.bloques_fecha.count(), 1)
        # El original se queda como estaba.
        self.assertEqual(h.bloques_semanales.count(), 1)

    def test_marcar_otro_como_default_suelta_el_anterior(self, _sync):
        nuevo = Horario.objects.create(host=self.host, nombre='Horario USA')
        self._cliente().post(self._url('horario_default', pk=nuevo.pk))
        nuevo.refresh_from_db()
        self.default.refresh_from_db()
        self.assertTrue(nuevo.es_default)
        self.assertFalse(self.default.es_default)
        self.assertEqual(Horario.objects.filter(host=self.host, es_default=True).count(), 1)

    def test_el_default_no_se_puede_borrar(self, _sync):
        self._cliente().post(self._url('horario_delete', pk=self.default.pk))
        self.assertTrue(Horario.objects.filter(pk=self.default.pk).exists())

    def test_borrar_horario_devuelve_sus_eventos_al_default(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Horario USA')
        self.etxh.horario = h
        self.etxh.save(update_fields=['horario'])

        self._cliente().post(self._url('horario_delete', pk=h.pk))

        self.etxh.refresh_from_db()
        self.assertIsNone(self.etxh.horario_id)

    def test_no_se_toca_el_horario_de_otra_persona(self, _sync):
        ajeno = crear_host(email='ajeno.horarios@test.com')
        suyo = Horario.objects.create(host=ajeno, nombre='Suyo')
        r = self._cliente().post(self._url('horario_rename', pk=suyo.pk), {'nombre': 'Robado'})
        self.assertEqual(r.status_code, 404)
        suyo.refresh_from_db()
        self.assertEqual(suyo.nombre, 'Suyo')

    # --- Asignación a tipos de evento ---

    def test_get_eventos_lista_los_del_host(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Horario USA')
        datos = self._cliente().get(self._url('horario_eventos', pk=h.pk)).json()
        nombres = {e['nombre'] for e in datos['eventos']}
        self.assertEqual(nombres, {'Evento panel', 'Otro panel'})
        self.assertTrue(all(e['usa_este'] is False for e in datos['eventos']))

    def test_get_lista_tambien_los_eventos_sin_fila_en_el_pool(self, _sync):
        # Un evento personal no tiene fila en EventTypeXHost —el motor cae al
        # dueño— pero tiene que poder recibir un horario igualmente.
        suelto = EventType.objects.create(
            host=self.host, nombre='Evento suelto', duracion_minutos=30, activo=True,
        )
        EventTypeXHost.objects.filter(event_type=suelto).delete()
        h = Horario.objects.create(host=self.host, nombre='Horario USA')

        datos = self._cliente().get(self._url('horario_eventos', pk=h.pk)).json()
        self.assertIn('Evento suelto', {e['nombre'] for e in datos['eventos']})

    def test_no_lista_eventos_de_equipo_donde_no_esta_en_el_pool(self, _sync):
        # Ser dueño de un evento de equipo sin estar en su pool no da horas: esa
        # persona no atiende ese evento.
        otro = crear_host(email='companero.pool@test.com')
        equipo = EventType.objects.create(
            host=self.host, nombre='Evento de equipo', duracion_minutos=30, activo=True,
        )
        EventTypeXHost.objects.filter(event_type=equipo).delete()
        EventTypeXHost.objects.create(event_type=equipo, host=otro)
        h = Horario.objects.create(host=self.host, nombre='Horario USA')

        datos = self._cliente().get(self._url('horario_eventos', pk=h.pk)).json()
        self.assertNotIn('Evento de equipo', {e['nombre'] for e in datos['eventos']})

    def test_asignar_no_mete_al_host_en_un_pool_ajeno(self, _sync):
        # Colar el id igualmente no debe crear la fila: entraría en el reparto
        # de round-robin por la puerta de atrás.
        otro = crear_host(email='companero.pool2@test.com')
        equipo = EventType.objects.create(
            host=self.host, nombre='Evento de equipo', duracion_minutos=30, activo=True,
        )
        EventTypeXHost.objects.filter(event_type=equipo).delete()
        EventTypeXHost.objects.create(event_type=equipo, host=otro)
        h = Horario.objects.create(host=self.host, nombre='Horario USA')

        self._cliente().post(
            self._url('horario_eventos', pk=h.pk),
            data={'event_type_ids': [equipo.pk]},
            content_type='application/json',
        )

        self.assertFalse(
            EventTypeXHost.objects.filter(event_type=equipo, host=self.host).exists()
        )
        self.assertEqual(EventTypeXHost.objects.filter(event_type=equipo).count(), 1)

    def test_asignar_a_un_evento_sin_fila_la_crea(self, _sync):
        suelto = EventType.objects.create(
            host=self.host, nombre='Evento suelto', duracion_minutos=30, activo=True,
        )
        EventTypeXHost.objects.filter(event_type=suelto).delete()
        h = Horario.objects.create(host=self.host, nombre='Horario USA')

        self._cliente().post(
            self._url('horario_eventos', pk=h.pk),
            data={'event_type_ids': [suelto.pk]},
            content_type='application/json',
        )

        etxh = EventTypeXHost.objects.get(event_type=suelto, host=self.host)
        self.assertEqual(etxh.horario_id, h.pk)
        self.assertEqual(etxh.prioridad, EventTypeXHost.PRIORIDAD_DEFECTO)

    def test_asignar_a_varios_eventos_de_una_vez(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Horario USA')
        r = self._cliente().post(
            self._url('horario_eventos', pk=h.pk),
            data={'event_type_ids': [self.et.pk, self.otro_et.pk]},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.etxh.refresh_from_db()
        self.otro_etxh.refresh_from_db()
        self.assertEqual(self.etxh.horario_id, h.pk)
        self.assertEqual(self.otro_etxh.horario_id, h.pk)

    def test_desmarcar_devuelve_al_default(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Horario USA')
        EventTypeXHost.objects.filter(host=self.host).update(horario=h)

        self._cliente().post(
            self._url('horario_eventos', pk=h.pk),
            data={'event_type_ids': [self.et.pk]},
            content_type='application/json',
        )

        self.etxh.refresh_from_db()
        self.otro_etxh.refresh_from_db()
        self.assertEqual(self.etxh.horario_id, h.pk)
        self.assertIsNone(self.otro_etxh.horario_id)

    def test_asignar_no_pisa_los_eventos_de_otro_horario(self, _sync):
        # Guardar el horario A no debe soltar lo que tenía asignado el B.
        a = Horario.objects.create(host=self.host, nombre='A')
        b = Horario.objects.create(host=self.host, nombre='B')
        self.otro_etxh.horario = b
        self.otro_etxh.save(update_fields=['horario'])

        self._cliente().post(
            self._url('horario_eventos', pk=a.pk),
            data={'event_type_ids': [self.et.pk]},
            content_type='application/json',
        )

        self.otro_etxh.refresh_from_db()
        self.assertEqual(self.otro_etxh.horario_id, b.pk)

    def test_el_get_avisa_de_que_el_evento_usa_otro_horario(self, _sync):
        a = Horario.objects.create(host=self.host, nombre='A')
        b = Horario.objects.create(host=self.host, nombre='B')
        self.etxh.horario = b
        self.etxh.save(update_fields=['horario'])

        datos = self._cliente().get(self._url('horario_eventos', pk=a.pk)).json()
        fila = next(e for e in datos['eventos'] if e['event_type_id'] == self.et.pk)
        self.assertEqual(fila['otro_horario'], 'B')

    def test_no_se_asignan_eventos_de_otra_persona(self, _sync):
        ajeno = crear_host(email='ajeno.eventos@test.com')
        et_ajeno = crear_event_type(ajeno, nombre='Ajeno', duracion=30)
        etxh_ajeno = EventTypeXHost.objects.get(event_type=et_ajeno, host=ajeno)
        h = Horario.objects.create(host=self.host, nombre='Horario USA')

        self._cliente().post(
            self._url('horario_eventos', pk=h.pk),
            data={'event_type_ids': [et_ajeno.pk]},
            content_type='application/json',
        )

        etxh_ajeno.refresh_from_db()
        self.assertIsNone(etxh_ajeno.horario_id)

    def test_payload_invalido_devuelve_400(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Horario USA')
        r = self._cliente().post(
            self._url('horario_eventos', pk=h.pk),
            data='esto no es json',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# 5. La pantalla de disponibilidad trabaja sobre el horario elegido
# ---------------------------------------------------------------------------

@patch(PATCH_SYNC)
class PantallaDisponibilidadPorHorarioTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.pantalla.horarios@test.com')
        self.default = horario_default(self.host)
        BloqueHorarioSemanal.objects.filter(horario__host=self.host).delete()
        self.usa = Horario.objects.create(host=self.host, nombre='Horario USA')
        self.url = reverse('panel_disponibilidad:bloque_list')

    def _cliente(self):
        c = Client()
        c.force_login(self.host)
        return c

    def test_sin_parametro_abre_el_default(self, _sync):
        ctx = self._cliente().get(self.url).context
        self.assertEqual(ctx['horario_objetivo'].pk, self.default.pk)

    def test_con_parametro_abre_el_pedido(self, _sync):
        ctx = self._cliente().get(self.url, {'horario': self.usa.pk}).context
        self.assertEqual(ctx['horario_objetivo'].pk, self.usa.pk)

    def test_el_horario_de_otra_persona_no_se_abre(self, _sync):
        ajeno = crear_host(email='ajeno.pantalla@test.com')
        suyo = Horario.objects.create(host=ajeno, nombre='Suyo')
        ctx = self._cliente().get(self.url, {'horario': suyo.pk}).context
        self.assertEqual(ctx['horario_objetivo'].pk, self.default.pk)

    def test_cada_horario_lleva_su_lapiz_menos_el_default(self, _sync):
        html = self._cliente().get(self.url).content.decode()
        # El "Horario USA" se puede renombrar...
        self.assertIn(f'data-horario="{self.usa.pk}"', html)
        self.assertIn(
            reverse('panel_disponibilidad:horario_rename', kwargs={'pk': self.usa.pk}), html
        )
        # ...y el Default no: su nombre es el que la app enseña en todas partes.
        self.assertNotIn(f'data-horario="{self.default.pk}"', html)
        self.assertNotIn(
            reverse('panel_disponibilidad:horario_rename', kwargs={'pk': self.default.pk}), html
        )

    def test_renombrar_desde_el_desplegable_deja_el_nombre_nuevo(self, _sync):
        self._cliente().post(
            reverse('panel_disponibilidad:horario_rename', kwargs={'pk': self.usa.pk}),
            {'nombre': 'Horario mañanas'},
        )
        self.usa.refresh_from_db()
        self.assertEqual(self.usa.nombre, 'Horario mañanas')

    def test_renombrar_una_copia_no_choca_con_el_original(self, _sync):
        # El caso que lo destapó: duplicar deja "X (copia)" y hay que poder
        # ponerle un nombre propio.
        copia = Horario.objects.create(host=self.host, nombre='Horario USA (copia)')
        self._cliente().post(
            reverse('panel_disponibilidad:horario_rename', kwargs={'pk': copia.pk}),
            {'nombre': 'Horario tardes'},
        )
        copia.refresh_from_db()
        self.assertEqual(copia.nombre, 'Horario tardes')

    def test_renombrar_con_un_nombre_ya_usado_no_rompe(self, _sync):
        copia = Horario.objects.create(host=self.host, nombre='Horario USA (copia)')
        self._cliente().post(
            reverse('panel_disponibilidad:horario_rename', kwargs={'pk': copia.pk}),
            {'nombre': 'Horario USA'},
        )
        copia.refresh_from_db()
        self.assertEqual(copia.nombre, 'Horario USA (2)')
        self.assertEqual(Horario.objects.filter(host=self.host).count(), 3)

    def test_renombrar_sin_nombre_lo_deja_como_estaba(self, _sync):
        self._cliente().post(
            reverse('panel_disponibilidad:horario_rename', kwargs={'pk': self.usa.pk}),
            {'nombre': '   '},
        )
        self.usa.refresh_from_db()
        self.assertEqual(self.usa.nombre, 'Horario USA')

    def test_solo_lista_los_bloques_del_horario_abierto(self, _sync):
        _franja(self.default, 0, time(9, 0), time(10, 0))
        _franja(self.usa, 0, time(15, 0), time(16, 0))

        bloques = self._cliente().get(self.url, {'horario': self.usa.pk}).context['bloques']
        self.assertEqual([b.hora_inicio for b in bloques], [time(15, 0)])

    def test_crear_un_bloque_lo_deja_en_el_horario_abierto(self, _sync):
        self._cliente().post(
            reverse('panel_disponibilidad:bloque_create'),
            {'dia_semana': 0, 'hora_inicio': '09:00', 'hora_fin': '10:00',
             'horario': self.usa.pk},
        )
        self.assertEqual(BloqueHorarioSemanal.objects.filter(horario=self.usa).count(), 1)
        self.assertEqual(BloqueHorarioSemanal.objects.filter(horario=self.default).count(), 0)

    def test_marcar_una_fecha_como_cerrada(self, _sync):
        fecha = timezone.localdate() + timedelta(days=3)
        self._cliente().post(
            reverse('panel_disponibilidad:bloque_fecha_create'),
            {'fechas': fecha.isoformat(), 'cerrado': '1', 'horario': self.usa.pk},
        )
        bloque = BloqueHorarioFecha.objects.get(horario=self.usa, fecha=fecha)
        self.assertTrue(bloque.cerrado)

    def test_cerrar_una_fecha_borra_las_horas_que_tuviera(self, _sync):
        fecha = timezone.localdate() + timedelta(days=3)
        _fecha(self.usa, fecha, time(9, 0), time(10, 0))

        self._cliente().post(
            reverse('panel_disponibilidad:bloque_fecha_create'),
            {'fechas': fecha.isoformat(), 'cerrado': '1', 'horario': self.usa.pk},
        )

        bloques = BloqueHorarioFecha.objects.filter(horario=self.usa, fecha=fecha)
        self.assertEqual(bloques.count(), 1)
        self.assertTrue(bloques.first().cerrado)


# ---------------------------------------------------------------------------
# 6. La ficha del tipo de evento dice qué horario usa cada organizador
# ---------------------------------------------------------------------------

@patch(PATCH_SYNC)
class FichaEventoMuestraHorarioTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.ficha.horarios@test.com')
        self.admin = User.objects.create_user(
            email='admin.ficha@test.com', username='admin_ficha',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.et = crear_event_type(self.host, nombre='Evento ficha', duracion=30)
        self.etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.host)
        self.url = reverse('panel_event_types:event_type_update', kwargs={'pk': self.et.pk})

    def _cliente(self):
        c = Client()
        c.force_login(self.admin)
        return c

    def test_sin_horario_asignado_no_dice_nada(self, _sync):
        html = self._cliente().get(self.url).content.decode()
        self.assertNotIn('Horarios en uso', html)

    def test_con_horario_asignado_lo_nombra(self, _sync):
        h = Horario.objects.create(host=self.host, nombre='Horario USA')
        self.etxh.horario = h
        self.etxh.save(update_fields=['horario'])

        html = self._cliente().get(self.url).content.decode()
        self.assertIn('Horarios en uso', html)
        self.assertIn('Horario USA', html)


# ---------------------------------------------------------------------------
# 7. El endpoint JSON responde JSON también cuando dice que no
# ---------------------------------------------------------------------------

@patch(PATCH_SYNC)
class EndpointEventosRespondeJsonTest(TestCase):

    def setUp(self):
        from calendario.grupos.models import Grupo, GrupoXUsuario
        self.host = crear_host(email='host.bloqueado@test.com')
        self.grupo = Grupo.objects.create(
            nombre='Bloqueados', bloquear_editar_disponibilidad=True,
        )
        GrupoXUsuario.objects.create(grupo=self.grupo, usuario=self.host)
        self.horario = Horario.objects.create(host=self.host, nombre='Horario USA')
        self.url = reverse('panel_disponibilidad:horario_eventos', kwargs={'pk': self.horario.pk})

    def test_grupo_bloqueado_recibe_json_no_un_redirect(self, _sync):
        # El JS del modal hace r.json(): un redirect a HTML le deja un mensaje
        # incomprensible en vez del motivo real.
        c = Client()
        c.force_login(self.host)
        r = c.post(self.url, data={'event_type_ids': []}, content_type='application/json')

        self.assertEqual(r.status_code, 403)
        self.assertEqual(r['Content-Type'], 'application/json')
        self.assertIn('error', r.json())


# ---------------------------------------------------------------------------
# 8. Editar el horario de otra persona (admin / supervisor)
# ---------------------------------------------------------------------------

@patch(PATCH_SYNC)
class HorarioDeOtraPersonaTest(TestCase):
    """
    Un admin que edita la disponibilidad de otro entra con `?host=<pk>`. Todo lo
    que salga de esa pantalla tiene que arrastrar ese parámetro, o el backend
    resuelve al usuario logueado y no encuentra nada.
    """

    def setUp(self):
        self.otro = crear_host(email='brynja@test.com', first_name='Brynja', last_name='Turner')
        self.admin = User.objects.create_user(
            email='admin.otro@test.com', username='admin_otro',
            password='test1234', is_active=True, is_superuser=True,
        )
        self.horario = horario_default(self.otro)
        self.et = crear_event_type(self.otro, nombre='Evento de Brynja', duracion=30)
        self.url = reverse(
            'panel_disponibilidad:horario_eventos', kwargs={'pk': self.horario.pk}
        )

    def _cliente(self):
        c = Client()
        c.force_login(self.admin)
        return c

    def test_get_con_host_lista_los_eventos_de_esa_persona(self, _sync):
        r = self._cliente().get(self.url, {'host': self.otro.pk})
        self.assertEqual(r.status_code, 200)
        self.assertIn('Evento de Brynja', {e['nombre'] for e in r.json()['eventos']})

    def test_get_sin_host_no_encuentra_el_horario_ajeno(self, _sync):
        # Este era el 404 que veía el usuario: sin `?host=` el backend busca el
        # horario entre los del admin, no entre los de Brynja.
        self.assertEqual(self._cliente().get(self.url).status_code, 404)

    def test_post_con_host_asigna_el_horario_de_esa_persona(self, _sync):
        r = self._cliente().post(
            f'{self.url}?host={self.otro.pk}',
            data={'event_type_ids': [self.et.pk]},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.otro)
        self.assertEqual(etxh.horario_id, self.horario.pk)

    def test_la_pantalla_pasa_el_host_en_la_url_del_boton(self, _sync):
        html = self._cliente().get(
            reverse('panel_disponibilidad:bloque_list'), {'host': self.otro.pk}
        ).content.decode()
        self.assertIn(f'{self.url}?host={self.otro.pk}', html)

