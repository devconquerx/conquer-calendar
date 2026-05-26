"""
Tests para horarios específicos por fecha (date-specific hours estilo Calendly).

Cubre:
- Modelo BloqueHorarioFecha: validación de clean() y constraints de BD.
- Motor de slots: un override por fecha SOBRESCRIBE el horario semanal de ese día,
  funciona con multi-rango, no se filtra a otras fechas y habilita días que de otro
  modo estarían sin disponibilidad.
- Vistas: render del panel, serialización de datos del calendario, alta (multi-rango,
  multi-fecha, reemplazo), validaciones, borrado y limpiar fecha.
- Permisos: ver/editar requieren los permisos correspondientes.

Nota: al crear un usuario, un signal post_save siembra disponibilidad semanal por
defecto (Lun–Vie). Los tests de slots la limpian con _reset_semanal() para ser
deterministas independientemente del día en que se ejecuten.
"""
from datetime import time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from calendario.availability.models import BloqueHorarioSemanal, BloqueHorarioFecha
from calendario.bookings.services import calcular_slots
from calendario.users.models import User
from tests.factories import crear_host, crear_event_type, crear_disponibilidad

TZ = 'America/Bogota'


def _reset_semanal(host):
    """Borra la disponibilidad semanal por defecto (sembrada por el signal)."""
    BloqueHorarioSemanal.objects.filter(host=host).delete()


def _horas_locales(slots):
    return sorted({s.astimezone(ZoneInfo(TZ)).hour for s in slots})


# ---------------------------------------------------------------------------
# 1. Modelo: validación y constraints
# ---------------------------------------------------------------------------

class BloqueHorarioFechaModelTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.model@test.com')
        self.fecha = timezone.localdate() + timedelta(days=3)

    def test_str_incluye_fecha_y_horas(self):
        b = BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        self.assertIn(self.fecha.isoformat(), str(b))
        self.assertIn('09:00', str(b))

    def test_clean_rechaza_fin_menor_o_igual_a_inicio(self):
        b = BloqueHorarioFecha(
            host=self.host, fecha=self.fecha, hora_inicio=time(10, 0), hora_fin=time(9, 0),
        )
        with self.assertRaises(ValidationError):
            b.clean()

    def test_clean_rechaza_solape_en_misma_fecha(self):
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(9, 0), hora_fin=time(12, 0),
        )
        b = BloqueHorarioFecha(
            host=self.host, fecha=self.fecha, hora_inicio=time(11, 0), hora_fin=time(13, 0),
        )
        with self.assertRaises(ValidationError):
            b.clean()

    def test_clean_permite_rangos_contiguos(self):
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(9, 0), hora_fin=time(12, 0),
        )
        b = BloqueHorarioFecha(
            host=self.host, fecha=self.fecha, hora_inicio=time(12, 0), hora_fin=time(14, 0),
        )
        b.clean()  # no debe lanzar

    def test_clean_permite_mismo_rango_en_otra_fecha(self):
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        b = BloqueHorarioFecha(
            host=self.host, fecha=self.fecha + timedelta(days=1),
            hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        b.clean()  # no debe lanzar

    def test_constraint_bd_fin_mayor_que_inicio(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BloqueHorarioFecha.objects.create(
                    host=self.host, fecha=self.fecha,
                    hora_inicio=time(15, 0), hora_fin=time(15, 0),
                )

    def test_constraint_bd_unico_host_fecha_rango(self):
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BloqueHorarioFecha.objects.create(
                    host=self.host, fecha=self.fecha,
                    hora_inicio=time(9, 0), hora_fin=time(10, 0),
                )


# ---------------------------------------------------------------------------
# 2. Motor de slots: comportamiento de override
# ---------------------------------------------------------------------------

@patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[])
class SlotsOverrideFechaTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='host.override@test.com')
        self.host.timezone = TZ
        self.host.save(update_fields=['timezone'])
        _reset_semanal(self.host)
        self.et = crear_event_type(self.host, duracion=60)
        self.fecha = timezone.localdate() + timedelta(days=5)
        crear_disponibilidad(
            self.host, dia=self.fecha.weekday(), inicio=time(9, 0), fin=time(17, 0),
        )

    def test_override_reemplaza_horario_semanal(self, _mock_busy):
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(13, 0), hora_fin=time(15, 0),
        )
        slots = calcular_slots(self.et, self.fecha, self.fecha)
        # Solo el rango específico 13–15 (slots 60 min: 13–14, 14–15).
        self.assertEqual(_horas_locales(slots), [13, 14])

    def test_sin_override_usa_horario_semanal(self, _mock_busy):
        slots = calcular_slots(self.et, self.fecha, self.fecha)
        self.assertEqual(_horas_locales(slots), list(range(9, 17)))

    def test_override_multi_rango_genera_slots_en_ambos(self, _mock_busy):
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(9, 0), hora_fin=time(11, 0),
        )
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(15, 0), hora_fin=time(17, 0),
        )
        slots = calcular_slots(self.et, self.fecha, self.fecha)
        self.assertEqual(_horas_locales(slots), [9, 10, 15, 16])

    def test_override_solo_afecta_su_propia_fecha(self, _mock_busy):
        # Mismo día de semana 7 días después: NO debe verse afectado por el override.
        siguiente = self.fecha + timedelta(days=7)
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=self.fecha, hora_inicio=time(13, 0), hora_fin=time(15, 0),
        )
        slots = calcular_slots(self.et, self.fecha, siguiente)
        tz = ZoneInfo(TZ)
        horas_fecha = sorted({s.astimezone(tz).hour for s in slots
                              if s.astimezone(tz).date() == self.fecha})
        horas_sig = sorted({s.astimezone(tz).hour for s in slots
                           if s.astimezone(tz).date() == siguiente})
        self.assertEqual(horas_fecha, [13, 14])           # override
        self.assertEqual(horas_sig, list(range(9, 17)))    # semanal intacto

    def test_override_habilita_dia_sin_disponibilidad_semanal(self, _mock_busy):
        # Día con weekday SIN disponibilidad semanal: sin override no hay slots,
        # con override sí. Demuestra que el override habilita disponibilidad nueva.
        libre = self.fecha + timedelta(days=1)
        self.assertEqual(calcular_slots(self.et, libre, libre), [])

        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=libre, hora_inicio=time(10, 0), hora_fin=time(12, 0),
        )
        slots = calcular_slots(self.et, libre, libre)
        self.assertEqual(_horas_locales(slots), [10, 11])


# ---------------------------------------------------------------------------
# 3. Vistas: render + CRUD
# ---------------------------------------------------------------------------

class HorasFechaViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host(email='host.view@test.com')
        self.client.force_login(self.host)
        self.create_url = reverse('panel_disponibilidad:bloque_fecha_create')

    def test_panel_renderiza_con_botones(self):
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Horas específicas')
        self.assertContains(resp, 'id="open-cal-modal"')

    def test_panel_serializa_datos_calendario(self):
        crear_disponibilidad(self.host, dia=0, inicio=time(9, 0), fin=time(17, 0))
        fecha = timezone.localdate() + timedelta(days=4)
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=fecha, hora_inicio=time(14, 0), hora_fin=time(15, 0),
        )
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        html = resp.content.decode()
        self.assertIn('id="weekly-data"', html)
        self.assertIn('id="overrides-data"', html)
        self.assertIn(fecha.isoformat(), html)
        self.assertIn('14:00', html)

    def test_panel_no_lista_overrides_pasados(self):
        pasada = timezone.localdate() - timedelta(days=2)
        futura = timezone.localdate() + timedelta(days=2)
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=pasada, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        BloqueHorarioFecha.objects.create(
            host=self.host, fecha=futura, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        fechas = [g['fecha'] for g in resp.context['fechas_agrupadas']]
        self.assertIn(futura, fechas)
        self.assertNotIn(pasada, fechas)

    def test_crear_override_multi_rango(self):
        fecha = (timezone.localdate() + timedelta(days=5)).isoformat()
        resp = self.client.post(self.create_url, {
            'fechas': fecha,
            'hora_inicio': ['09:00', '14:00'],
            'hora_fin': ['12:00', '16:00'],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            BloqueHorarioFecha.objects.filter(host=self.host, fecha=fecha).count(), 2
        )

    def test_crear_override_multi_fecha(self):
        f1 = (timezone.localdate() + timedelta(days=7)).isoformat()
        f2 = (timezone.localdate() + timedelta(days=8)).isoformat()
        resp = self.client.post(self.create_url, {
            'fechas': f'{f1},{f2}',
            'hora_inicio': ['10:00'],
            'hora_fin': ['11:00'],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host).count(), 2)

    def test_crear_override_reemplaza_existente(self):
        fecha = (timezone.localdate() + timedelta(days=6)).isoformat()
        self.client.post(self.create_url, {'fechas': fecha, 'hora_inicio': ['09:00'], 'hora_fin': ['12:00']})
        self.client.post(self.create_url, {'fechas': fecha, 'hora_inicio': ['15:00'], 'hora_fin': ['18:00']})
        bloques = BloqueHorarioFecha.objects.filter(host=self.host, fecha=fecha)
        self.assertEqual(bloques.count(), 1)
        self.assertEqual(bloques.first().hora_inicio, time(15, 0))

    def test_rango_invalido_no_crea(self):
        fecha = (timezone.localdate() + timedelta(days=9)).isoformat()
        resp = self.client.post(self.create_url, {
            'fechas': fecha, 'hora_inicio': ['15:00'], 'hora_fin': ['12:00'],  # fin <= inicio
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host).count(), 0)

    def test_rangos_solapados_no_crea(self):
        fecha = (timezone.localdate() + timedelta(days=10)).isoformat()
        resp = self.client.post(self.create_url, {
            'fechas': fecha,
            'hora_inicio': ['09:00', '10:00'],
            'hora_fin': ['11:00', '12:00'],  # 10–11 solapa con 09–11
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host).count(), 0)

    def test_sin_fechas_no_crea(self):
        resp = self.client.post(self.create_url, {
            'fechas': '', 'hora_inicio': ['09:00'], 'hora_fin': ['12:00'],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host).count(), 0)

    def test_fecha_invalida_se_ignora(self):
        resp = self.client.post(self.create_url, {
            'fechas': 'no-es-fecha', 'hora_inicio': ['09:00'], 'hora_fin': ['12:00'],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host).count(), 0)

    def test_borrar_override(self):
        fecha = timezone.localdate() + timedelta(days=10)
        bloque = BloqueHorarioFecha.objects.create(
            host=self.host, fecha=fecha, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        resp = self.client.post(
            reverse('panel_disponibilidad:bloque_fecha_delete', kwargs={'pk': bloque.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(BloqueHorarioFecha.objects.filter(pk=bloque.pk).exists())

    def test_no_puede_borrar_override_de_otro_host(self):
        otro = crear_host(email='otro.host@test.com')
        fecha = timezone.localdate() + timedelta(days=5)
        ajeno = BloqueHorarioFecha.objects.create(
            host=otro, fecha=fecha, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        )
        self.client.post(
            reverse('panel_disponibilidad:bloque_fecha_delete', kwargs={'pk': ajeno.pk})
        )
        self.assertTrue(BloqueHorarioFecha.objects.filter(pk=ajeno.pk).exists())


# ---------------------------------------------------------------------------
# 4. Vista limpiar fecha
# ---------------------------------------------------------------------------

class LimpiarFechaViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host(email='host.limpiar@test.com')
        self.client.force_login(self.host)

    def test_limpia_todos_los_rangos_de_la_fecha(self):
        fecha = timezone.localdate() + timedelta(days=5)
        otra = timezone.localdate() + timedelta(days=6)
        BloqueHorarioFecha.objects.create(host=self.host, fecha=fecha, hora_inicio=time(9, 0), hora_fin=time(10, 0))
        BloqueHorarioFecha.objects.create(host=self.host, fecha=fecha, hora_inicio=time(11, 0), hora_fin=time(12, 0))
        BloqueHorarioFecha.objects.create(host=self.host, fecha=otra, hora_inicio=time(9, 0), hora_fin=time(10, 0))

        resp = self.client.post(
            reverse('panel_disponibilidad:fecha_limpiar', kwargs={'fecha': fecha.isoformat()})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host, fecha=fecha).count(), 0)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.host, fecha=otra).count(), 1)

    def test_fecha_invalida_no_rompe(self):
        resp = self.client.post(
            reverse('panel_disponibilidad:fecha_limpiar', kwargs={'fecha': 'xxx'})
        )
        self.assertEqual(resp.status_code, 302)


# ---------------------------------------------------------------------------
# 5. Permisos
# ---------------------------------------------------------------------------

class PermisosHorasFechaTest(TestCase):

    def setUp(self):
        self.client = Client()
        # Usuario sin rol → sin permisos de availability.
        self.user = User.objects.create(
            email='sin.permisos@test.com', username='sinpermisos', is_active=True,
        )
        self.client.force_login(self.user)

    def test_anonimo_redirige_a_login(self):
        resp = Client().get(reverse('panel_disponibilidad:bloque_list'))
        self.assertEqual(resp.status_code, 302)

    def test_ver_sin_permiso_devuelve_403(self):
        resp = self.client.get(reverse('panel_disponibilidad:bloque_list'))
        self.assertEqual(resp.status_code, 403)

    def test_crear_sin_permiso_devuelve_403(self):
        fecha = (timezone.localdate() + timedelta(days=3)).isoformat()
        resp = self.client.post(reverse('panel_disponibilidad:bloque_fecha_create'), {
            'fechas': fecha, 'hora_inicio': ['09:00'], 'hora_fin': ['12:00'],
        })
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(BloqueHorarioFecha.objects.filter(host=self.user).count(), 0)
