"""
El cálculo de slots de un pool carga de una vez lo de todos sus hosts
(FUNNELS-CK/CM/CN/CT/CR/CP/D9/D4: cerca de cien queries sueltas por visita con
los 19 organizadores de Languages). Lo que importa es que ofrezca exactamente
las mismas horas que calculando host por host.
"""
from datetime import time, timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from calendario.availability.models import Horario
from calendario.bookings import services
from calendario.event_types.models import EventTypeXHost
from calendario.google_calendar.models import GoogleCalendarSyncEstado
from tests.factories import crear_disponibilidad, crear_event_type, crear_host

PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'
PATCH_BUSY_LOCAL = 'calendario.bookings.services.obtener_busy_intervalos_local'


@patch(PATCH_BUSY_LOCAL, return_value=[])
@patch(PATCH_BUSY, return_value=[])
class PrecargaHostsTest(TestCase):

    def setUp(self):
        self.hosts = [crear_host(f'host{i}@conquerx.com', first_name=f'H{i}') for i in range(4)]
        self.et = crear_event_type(self.hosts[0], nombre='Pool')
        for i, host in enumerate(self.hosts):
            EventTypeXHost.objects.get_or_create(event_type=self.et, host=host)
            for dia in range(7):
                crear_disponibilidad(host, dia=dia, inicio=time(8 + i, 0), fin=time(10 + i, 0))
        # Uno con un horario propio para este evento, que manda sobre su default.
        propio = Horario.objects.create(host=self.hosts[1], nombre='Solo tardes')
        for dia in range(7):
            crear_disponibilidad(self.hosts[1], dia=dia, inicio=time(16, 0), fin=time(17, 0), horario=propio)
        EventTypeXHost.objects.filter(event_type=self.et, host=self.hosts[1]).update(horario=propio)
        # Y uno con sync activo, que lee la copia local en vez de freeBusy.
        GoogleCalendarSyncEstado.objects.update_or_create(
            host=self.hosts[2], defaults={'estado': GoogleCalendarSyncEstado.ACTIVO})
        self.desde = timezone.now().date() + timedelta(days=1)
        self.hasta = self.desde + timedelta(days=6)

    def _host_por_host(self):
        slots = set()
        for host in self.hosts:
            slots.update(services._calcular_slots_para_host(self.et, host, self.desde, self.hasta))
        return slots

    def test_con_precarga_salen_las_mismas_horas(self, busy, busy_local):
        precarga = services._precargar_hosts(self.et, self.hosts)
        con_precarga = set()
        for host in self.hosts:
            con_precarga.update(services._calcular_slots_para_host(
                self.et, host, self.desde, self.hasta, precarga=precarga[host.pk]))

        self.assertTrue(con_precarga)
        self.assertEqual(con_precarga, self._host_por_host())
        self.assertIs(precarga[self.hosts[2].pk]['sync_activo'], True)
        self.assertEqual(precarga[self.hosts[1].pk]['horario'].nombre, 'Solo tardes')

    def test_la_precarga_no_crece_con_el_pool(self, busy, busy_local):
        with CaptureQueriesContext(connection) as q:
            services._precargar_hosts(self.et, self.hosts)
        self.assertLessEqual(len(q), 4)

    def test_el_host_con_sync_va_a_la_copia_local(self, busy, busy_local):
        precarga = services._precargar_hosts(self.et, self.hosts)
        services._calcular_slots_para_host(self.et, self.hosts[2], self.desde, self.hasta,
                                           precarga=precarga[self.hosts[2].pk])
        busy_local.assert_called_once()
        busy.assert_not_called()
