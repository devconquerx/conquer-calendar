"""
Tests para DisponibilidadEtxh y DisponibilidadFechaEtxh.

Cubre:
- Motor de slots: si un EventTypeXHost tiene disponibilidad propia, reemplaza
  el BloqueHorarioSemanal global para ese evento/host.
- Motor de slots: DisponibilidadFechaEtxh reemplaza la franja semanal del etxh
  para fechas concretas (o bloquea el día si no hay horas).
- Aislamiento: la disponibilidad de un evento no afecta a otros eventos del mismo host.
- Sin configuración etxh: sigue usando el horario global del host.
- Multi-franja por día.
- API JSON (GET/POST): persistencia y permisos.
"""
import json
from datetime import time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from calendario.availability.models import BloqueHorarioSemanal
from calendario.bookings.services import calcular_slots
from calendario.event_types.models import (
    EventType, EventTypeXHost,
    DisponibilidadEtxh, DisponibilidadFechaEtxh,
)
from calendario.users.models import User
from tests.factories import crear_host, crear_event_type, crear_disponibilidad

TZ = 'America/Bogota'
PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'
PATCH_SYNC = 'calendario.google_calendar.sync.sincronizar_host_completo'


def _reset_semanal(host):
    BloqueHorarioSemanal.objects.filter(host=host).delete()


def _horas_locales(slots, tz=TZ):
    return sorted({s.astimezone(ZoneInfo(tz)).hour for s in slots})


def _lunes_proximo():
    """Devuelve siempre el próximo lunes (nunca hoy aunque hoy sea lunes)."""
    hoy = timezone.localdate()
    dias = (7 - hoy.weekday()) % 7 or 7
    return hoy + timedelta(days=dias)


def _proximo_dia(dia_semana):
    hoy = timezone.localdate()
    dias = (dia_semana - hoy.weekday()) % 7 or 7
    return hoy + timedelta(days=dias)


def _crear_etxh_disp(host, et, dia, inicio, fin):
    etxh = EventTypeXHost.objects.get(event_type=et, host=host)
    return DisponibilidadEtxh.objects.create(
        etxh=etxh, dia_semana=dia, hora_inicio=inicio, hora_fin=fin,
    )


def _crear_fecha_disp(host, et, fecha, inicio=None, fin=None):
    etxh = EventTypeXHost.objects.get(event_type=et, host=host)
    return DisponibilidadFechaEtxh.objects.create(
        etxh=etxh, fecha=fecha, hora_inicio=inicio, hora_fin=fin,
    )


# ---------------------------------------------------------------------------
# 1. Motor de slots — horario semanal por evento
# ---------------------------------------------------------------------------

@patch(PATCH_BUSY, return_value=[])
class SlotsDisponibilidadEtxhSemanalTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.etxh@test.com')
        self.host.timezone = TZ
        self.host.save(update_fields=['timezone'])
        _reset_semanal(self.host)
        self.et = crear_event_type(self.host, nombre='Evento Etxh', duracion=60)

    def test_sin_disp_etxh_usa_bloque_semanal_global(self, _busy):
        dia = _proximo_dia(0)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(11, 0))
        slots = calcular_slots(self.et, dia, dia)
        self.assertEqual(_horas_locales(slots), [9, 10])

    def test_con_disp_etxh_ignora_bloque_global(self, _busy):
        # Global: lunes 9–11. Etxh: lunes 14–16. Deben salir solo 14 y 15.
        lunes = _proximo_dia(0)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(11, 0))
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(14, 0), fin=time(16, 0))
        slots = calcular_slots(self.et, lunes, lunes)
        self.assertEqual(_horas_locales(slots), [14, 15])

    def test_dia_sin_disp_etxh_no_genera_slots_aunque_haya_global(self, _busy):
        # Global tiene martes, pero etxh solo configura lunes → martes sin slots.
        lunes = _proximo_dia(0)
        martes = _proximo_dia(1)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(11, 0))
        crear_disponibilidad(self.host, dia=1, inicio=time(9, 0), fin=time(11, 0))
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(10, 0), fin=time(12, 0))
        slots = calcular_slots(self.et, lunes, martes)
        tz = ZoneInfo(TZ)
        fechas_con_slots = {s.astimezone(tz).date() for s in slots}
        self.assertIn(lunes, fechas_con_slots)
        self.assertNotIn(martes, fechas_con_slots)

    def test_multi_franja_por_dia(self, _busy):
        # Mañana 9–11 y tarde 15–17 → 4 slots de 60 min.
        lunes = _proximo_dia(0)
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(9, 0), fin=time(11, 0))
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(15, 0), fin=time(17, 0))
        slots = calcular_slots(self.et, lunes, lunes)
        self.assertEqual(_horas_locales(slots), [9, 10, 15, 16])

    def test_otro_evento_mismo_host_no_se_ve_afectado(self, _busy):
        # et2 no tiene disp etxh → usa el global. et tiene disp etxh limitada.
        lunes = _proximo_dia(0)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(12, 0))
        # et: solo 14–15 (hora fuera del global para distinguirla)
        _reset_semanal(self.host)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(12, 0))
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(14, 0), fin=time(15, 0))

        et2 = crear_event_type(self.host, nombre='Evento sin config', duracion=60)
        slots_et = calcular_slots(self.et, lunes, lunes)
        slots_et2 = calcular_slots(et2, lunes, lunes)

        self.assertEqual(_horas_locales(slots_et), [14])
        self.assertEqual(_horas_locales(slots_et2), [9, 10, 11])

    def test_disp_etxh_en_varios_dias(self, _busy):
        # Usa el próximo lunes como ancla; miércoles = lunes + 2 (siempre ordenado).
        lunes = _lunes_proximo()
        miercoles = lunes + timedelta(days=2)
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(9, 0), fin=time(10, 0))
        _crear_etxh_disp(self.host, self.et, dia=2, inicio=time(16, 0), fin=time(18, 0))
        slots = calcular_slots(self.et, lunes, miercoles)
        tz = ZoneInfo(TZ)
        horas_lunes = sorted({s.astimezone(tz).hour for s in slots if s.astimezone(tz).date() == lunes})
        horas_mierc = sorted({s.astimezone(tz).hour for s in slots if s.astimezone(tz).date() == miercoles})
        self.assertEqual(horas_lunes, [9])
        self.assertEqual(horas_mierc, [16, 17])

    def test_etxh_sin_franjas_usa_global(self, _busy):
        # etxh existe pero sin DisponibilidadEtxh rows → usa BloqueHorarioSemanal.
        lunes = _proximo_dia(0)
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(10, 0))
        # No creamos DisponibilidadEtxh: el queryset devuelve lista vacía
        slots = calcular_slots(self.et, lunes, lunes)
        self.assertEqual(_horas_locales(slots), [9])


# ---------------------------------------------------------------------------
# 2. Motor de slots — fechas específicas por evento
# ---------------------------------------------------------------------------

@patch(PATCH_BUSY, return_value=[])
class SlotsDisponibilidadFechaEtxhTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.fecha.etxh@test.com')
        self.host.timezone = TZ
        self.host.save(update_fields=['timezone'])
        _reset_semanal(self.host)
        self.et = crear_event_type(self.host, nombre='Evento Fecha', duracion=60)
        self.fecha = _proximo_dia(0)  # próximo lunes
        # Base semanal del etxh: lunes 9–11
        _crear_etxh_disp(self.host, self.et, dia=0, inicio=time(9, 0), fin=time(11, 0))

    def test_fecha_disp_reemplaza_franja_semanal(self, _busy):
        # Semanal: 9–11. Override fecha: 14–16 → solo 14, 15.
        _crear_fecha_disp(self.host, self.et, self.fecha, time(14, 0), time(16, 0))
        slots = calcular_slots(self.et, self.fecha, self.fecha)
        self.assertEqual(_horas_locales(slots), [14, 15])

    def test_fecha_disp_sin_horas_bloquea_dia(self, _busy):
        # Override con hora_inicio=None → día bloqueado, sin slots.
        _crear_fecha_disp(self.host, self.et, self.fecha, None, None)
        slots = calcular_slots(self.et, self.fecha, self.fecha)
        self.assertEqual(slots, [])

    def test_fecha_disp_solo_afecta_su_fecha(self, _busy):
        # Override en lunes X → lunes X+7 sigue usando la franja semanal.
        siguiente_lunes = self.fecha + timedelta(days=7)
        _crear_fecha_disp(self.host, self.et, self.fecha, time(14, 0), time(16, 0))
        # Añadimos disponibilidad semanal para el siguiente lunes también
        slots = calcular_slots(self.et, self.fecha, siguiente_lunes)
        tz = ZoneInfo(TZ)
        horas_fecha = sorted({s.astimezone(tz).hour for s in slots if s.astimezone(tz).date() == self.fecha})
        horas_sig = sorted({s.astimezone(tz).hour for s in slots if s.astimezone(tz).date() == siguiente_lunes})
        self.assertEqual(horas_fecha, [14, 15])   # override
        self.assertEqual(horas_sig, [9, 10])       # semanal intacto

    def test_fecha_disp_etxh_tiene_prioridad_sobre_bloque_fecha_global(self, _busy):
        # BloqueHorarioFecha global dice 10–11, DisponibilidadFechaEtxh dice 14–15.
        # Debe ganar el del etxh.
        from calendario.availability.models import BloqueHorarioFecha
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha,
            hora_inicio=time(10, 0), hora_fin=time(11, 0),
        )
        _crear_fecha_disp(self.host, self.et, self.fecha, time(14, 0), time(15, 0))
        slots = calcular_slots(self.et, self.fecha, self.fecha)
        self.assertEqual(_horas_locales(slots), [14])

    def test_fecha_disp_etxh_habilita_dia_sin_franja_semanal(self, _busy):
        # El etxh no tiene franja semanal para martes, pero sí un override de fecha.
        martes = _proximo_dia(1)
        self.assertEqual(calcular_slots(self.et, martes, martes), [])
        _crear_fecha_disp(self.host, self.et, martes, time(10, 0), time(12, 0))
        slots = calcular_slots(self.et, martes, martes)
        self.assertEqual(_horas_locales(slots), [10, 11])


# ---------------------------------------------------------------------------
# 3. API JSON — endpoint disponibilidad_etxh_view
# ---------------------------------------------------------------------------

@patch(PATCH_SYNC)
class DisponibilidadEtxhApiTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.api.etxh@test.com')
        self.host.timezone = TZ
        self.host.save(update_fields=['timezone'])
        _reset_semanal(self.host)

        self.admin = User.objects.create_user(
            email='admin.etxh@test.com',
            username='admin_etxh',
            password='test1234',
            is_active=True,
            is_superuser=True,
        )

        self.et = crear_event_type(self.host, nombre='Evento API', duracion=30)
        self.etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.host)
        self.url = reverse(
            'panel_event_types:disponibilidad_etxh',
            kwargs={'pk': self.et.pk, 'host_pk': self.host.pk},
        )

    def _client_admin(self):
        c = Client()
        c.force_login(self.admin)
        return c

    def _client_host(self):
        c = Client()
        c.force_login(self.host)
        return c

    # --- GET ---

    def test_get_devuelve_listas_vacias_sin_config(self, _sync):
        data = self._client_admin().get(self.url).json()
        self.assertEqual(data['franjas'], [])
        self.assertEqual(data['fechas'], [])

    def test_get_devuelve_franjas_guardadas(self, _sync):
        DisponibilidadEtxh.objects.create(
            etxh=self.etxh, dia_semana=0,
            hora_inicio=time(9, 0), hora_fin=time(11, 0),
        )
        data = self._client_admin().get(self.url).json()
        self.assertEqual(len(data['franjas']), 1)
        self.assertEqual(data['franjas'][0]['dia_semana'], 0)
        self.assertEqual(data['franjas'][0]['hora_inicio'], '09:00')
        self.assertEqual(data['franjas'][0]['hora_fin'], '11:00')

    def test_get_devuelve_fechas_guardadas(self, _sync):
        fecha = timezone.localdate() + timedelta(days=5)
        DisponibilidadFechaEtxh.objects.create(
            etxh=self.etxh, fecha=fecha,
            hora_inicio=time(10, 0), hora_fin=time(12, 0),
        )
        data = self._client_admin().get(self.url).json()
        self.assertEqual(len(data['fechas']), 1)
        self.assertEqual(data['fechas'][0]['fecha'], fecha.isoformat())

    def test_get_403_para_no_admin(self, _sync):
        resp = self._client_host().get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_get_host_sin_etxh_devuelve_vacio(self, _sync):
        otro_host = crear_host(email='otro.api@test.com')
        url = reverse(
            'panel_event_types:disponibilidad_etxh',
            kwargs={'pk': self.et.pk, 'host_pk': otro_host.pk},
        )
        resp = self._client_admin().get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['franjas'], [])

    # --- POST ---

    def _post(self, client, franjas=None, fechas=None):
        return client.post(
            self.url,
            data=json.dumps({'franjas': franjas or [], 'fechas': fechas or []}),
            content_type='application/json',
        )

    def test_post_guarda_franjas(self, _sync):
        resp = self._post(self._client_admin(), franjas=[
            {'dia_semana': 1, 'hora_inicio': '09:00', 'hora_fin': '12:00'},
            {'dia_semana': 1, 'hora_inicio': '15:00', 'hora_fin': '17:00'},
        ])
        self.assertEqual(resp.json(), {'ok': True})
        self.assertEqual(DisponibilidadEtxh.objects.filter(etxh=self.etxh).count(), 2)

    def test_post_guarda_fechas(self, _sync):
        fecha = (timezone.localdate() + timedelta(days=4)).isoformat()
        resp = self._post(self._client_admin(), fechas=[
            {'fecha': fecha, 'hora_inicio': '10:00', 'hora_fin': '11:00'},
        ])
        self.assertEqual(resp.json(), {'ok': True})
        self.assertEqual(DisponibilidadFechaEtxh.objects.filter(etxh=self.etxh).count(), 1)

    def test_post_reemplaza_configuracion_anterior(self, _sync):
        self._post(self._client_admin(), franjas=[
            {'dia_semana': 0, 'hora_inicio': '09:00', 'hora_fin': '11:00'},
        ])
        self._post(self._client_admin(), franjas=[
            {'dia_semana': 2, 'hora_inicio': '14:00', 'hora_fin': '16:00'},
        ])
        franjas = list(DisponibilidadEtxh.objects.filter(etxh=self.etxh).values('dia_semana'))
        self.assertEqual(len(franjas), 1)
        self.assertEqual(franjas[0]['dia_semana'], 2)

    def test_post_guarda_fecha_bloqueada_sin_horas(self, _sync):
        fecha = (timezone.localdate() + timedelta(days=6)).isoformat()
        resp = self._post(self._client_admin(), fechas=[
            {'fecha': fecha, 'hora_inicio': None, 'hora_fin': None},
        ])
        self.assertEqual(resp.json(), {'ok': True})
        obj = DisponibilidadFechaEtxh.objects.get(etxh=self.etxh, fecha=fecha)
        self.assertIsNone(obj.hora_inicio)
        self.assertIsNone(obj.hora_fin)

    def test_post_403_para_no_admin(self, _sync):
        resp = self._post(self._client_host(), franjas=[
            {'dia_semana': 0, 'hora_inicio': '09:00', 'hora_fin': '11:00'},
        ])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(DisponibilidadEtxh.objects.filter(etxh=self.etxh).count(), 0)

    def test_post_payload_invalido_devuelve_400(self, _sync):
        c = self._client_admin()
        resp = c.post(self.url, data='not-json', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_post_dia_invalido_devuelve_400(self, _sync):
        resp = self._post(self._client_admin(), franjas=[
            {'dia_semana': 9, 'hora_inicio': '09:00', 'hora_fin': '11:00'},
        ])
        self.assertEqual(resp.status_code, 400)

    def test_get_post_round_trip(self, _sync):
        fecha = (timezone.localdate() + timedelta(days=3)).isoformat()
        self._post(self._client_admin(),
            franjas=[{'dia_semana': 3, 'hora_inicio': '08:00', 'hora_fin': '10:00'}],
            fechas=[{'fecha': fecha, 'hora_inicio': '13:00', 'hora_fin': '15:00'}],
        )
        data = self._client_admin().get(self.url).json()
        self.assertEqual(len(data['franjas']), 1)
        self.assertEqual(data['franjas'][0]['dia_semana'], 3)
        self.assertEqual(len(data['fechas']), 1)
        self.assertEqual(data['fechas'][0]['fecha'], fecha)


# ---------------------------------------------------------------------------
# 4. Modelo — __str__ y consistencia básica
# ---------------------------------------------------------------------------

class DisponibilidadEtxhModelTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.model.etxh@test.com')
        self.et = crear_event_type(self.host, nombre='Modelo Test', duracion=30)
        self.etxh = EventTypeXHost.objects.get(event_type=self.et, host=self.host)

    def test_str_disponibilidad_etxh(self):
        d = DisponibilidadEtxh.objects.create(
            etxh=self.etxh, dia_semana=0,
            hora_inicio=time(9, 0), hora_fin=time(17, 0),
        )
        s = str(d)
        self.assertIn('09:00', s)
        self.assertIn('17:00', s)

    def test_str_disponibilidad_fecha_con_horas(self):
        fecha = timezone.localdate() + timedelta(days=5)
        d = DisponibilidadFechaEtxh.objects.create(
            etxh=self.etxh, fecha=fecha,
            hora_inicio=time(10, 0), hora_fin=time(12, 0),
        )
        s = str(d)
        self.assertIn(fecha.isoformat(), s)
        self.assertIn('10:00', s)

    def test_str_disponibilidad_fecha_bloqueada(self):
        fecha = timezone.localdate() + timedelta(days=6)
        d = DisponibilidadFechaEtxh.objects.create(
            etxh=self.etxh, fecha=fecha, hora_inicio=None, hora_fin=None,
        )
        self.assertIn('Cerrado', str(d))

    def test_ordering_disponibilidad_etxh(self):
        DisponibilidadEtxh.objects.create(etxh=self.etxh, dia_semana=3, hora_inicio=time(9,0), hora_fin=time(10,0))
        DisponibilidadEtxh.objects.create(etxh=self.etxh, dia_semana=1, hora_inicio=time(9,0), hora_fin=time(10,0))
        dias = list(DisponibilidadEtxh.objects.filter(etxh=self.etxh).values_list('dia_semana', flat=True))
        self.assertEqual(dias, [1, 3])
