import datetime
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from calendario.availability.models import BloqueHorarioFecha, BloqueHorarioSemanal
from calendario.bookings.services import calcular_slots
from calendario.event_types.models import EventType
from calendario.google_calendar.models import GoogleCalendarSyncEstado
from calendario.google_calendar.services import (
    obtener_busy_intervalos,
    obtener_busy_intervalos_local,
)

User = get_user_model()

# Umbral mínimo para reportar un evento fantasma (evita ruido de gaps de <1h)
MIN_DURACION_FANTASMA_H = 1.0


def _solapa(ini_a, fin_a, intervalos):
    """True si [ini_a, fin_a) solapa con algún intervalo de la lista."""
    return any(b_ini < fin_a and b_fin > ini_a for b_ini, b_fin in intervalos)


def _analizar_solapamientos(intervalos):
    """
    Clasifica los solapamientos entre intervalos ordenados.
    Devuelve (duplicados, naturales):
      - duplicados: lista de intervalos que aparecen más de una vez (mismo inicio y fin)
      - naturales: True si hay solapamientos que NO son duplicados exactos
    """
    if len(intervalos) < 2:
        return [], False
    sorted_ivs = sorted(intervalos)
    duplicados = []
    hay_natural = False
    for i in range(len(sorted_ivs) - 1):
        a, b = sorted_ivs[i], sorted_ivs[i + 1]
        if b[0] < a[1]:  # se solapan
            if a == b:
                duplicados.append(a)
            else:
                hay_natural = True
    return duplicados, hay_natural


class Command(BaseCommand):
    help = (
        'Diagnóstico de disponibilidad y caché GCal. '
        'Compara los slots que calcula la app contra el freebusy real de Google Calendar '
        'y detecta caché desactualizada, disponibilidad sin configurar, webhooks caducados, etc.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=30,
            help='Días a analizar desde hoy (default: 30)',
        )
        parser.add_argument(
            '--host', type=str, default=None,
            help='Analizar solo este email de host',
        )
        parser.add_argument(
            '--output', type=str, default=None,
            help='Ruta del archivo .md de salida (default: diagnostico_YYYYMMDD.md en el directorio actual)',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        hoy = datetime.date.today()
        fecha_desde = hoy
        fecha_hasta = hoy + datetime.timedelta(days=dias)
        ahora_utc = timezone.now()
        inicio_utc = datetime.datetime(hoy.year, hoy.month, hoy.day, 0, 0, tzinfo=datetime.timezone.utc)
        fin_utc = datetime.datetime(fecha_hasta.year, fecha_hasta.month, fecha_hasta.day, 23, 59, tzinfo=datetime.timezone.utc)

        # Obtener hosts a analizar
        if options['host']:
            hosts = list(User.objects.filter(email=options['host'], is_active=True))
            if not hosts:
                self.stderr.write(self.style.ERROR(f"No existe usuario activo con email '{options['host']}'"))
                return
        else:
            host_ids = (
                EventType.objects
                .filter(activo=True, host__isnull=False)
                .values_list('host_id', flat=True)
                .distinct()
            )
            hosts = list(User.objects.filter(id__in=host_ids, is_active=True).order_by('email'))

        self.stdout.write(
            self.style.HTTP_INFO(
                f'\nDiagnóstico de disponibilidad — {hoy} — {len(hosts)} hosts — próximos {dias} días\n'
                + '=' * 70
            )
        )

        resultados = []
        for host in hosts:
            resultado = self._analizar_host(host, fecha_desde, fecha_hasta, inicio_utc, fin_utc, ahora_utc)
            resultados.append(resultado)
            self._imprimir_resultado(resultado)

        # Guardar .md
        output_path = options['output'] or f'diagnostico_{hoy.strftime("%Y%m%d")}.md'
        md = _generar_md(resultados, hoy, dias)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)
        self.stdout.write(f'\nReporte guardado en: {os.path.abspath(output_path)}')

    # ------------------------------------------------------------------
    # Análisis por host
    # ------------------------------------------------------------------

    def _analizar_host(self, host, fecha_desde, fecha_hasta, inicio_utc, fin_utc, ahora_utc):
        r = {
            'email': host.email,
            'problemas': [],
            'avisos': [],
            'event_types': [],
            'total_slots': 0,
            'gcal_ok': True,
        }

        # 1. Disponibilidad configurada
        tiene_semanal = BloqueHorarioSemanal.objects.filter(host=host).exists()
        tiene_fecha_futura = BloqueHorarioFecha.objects.filter(host=host, fecha__gte=fecha_desde).exists()
        if not tiene_semanal and not tiene_fecha_futura:
            r['avisos'].append('SIN_DISPONIBILIDAD — no tiene bloques semanales ni fechas futuras configuradas')

        # 2. Estado del sync y webhook
        try:
            sync = GoogleCalendarSyncEstado.objects.get(host=host)
            if sync.estado == GoogleCalendarSyncEstado.ERROR:
                r['problemas'].append('SYNC_ERROR — el sync de GCal está en estado error')
            if sync.canal_expira_utc:
                dias_exp = (sync.canal_expira_utc - ahora_utc).total_seconds() / 86400
                if dias_exp < 0:
                    r['problemas'].append(f'WEBHOOK_EXPIRADO — caducó hace {int(abs(dias_exp))} días')
                elif dias_exp < 2:
                    r['avisos'].append(f'WEBHOOK_PRONTO — expira en {int(dias_exp * 24)}h')
            elif not sync.canal_id:
                r['avisos'].append('SIN_WEBHOOK — canal de notificaciones no registrado')
        except GoogleCalendarSyncEstado.DoesNotExist:
            r['problemas'].append('SIN_SYNC — no tiene registro GoogleCalendarSyncEstado')

        # 3. Freebusy real de GCal (una sola llamada por host)
        busy_gcal = obtener_busy_intervalos(host.email, inicio_utc, fin_utc)
        if busy_gcal is None:
            busy_gcal = []
            r['gcal_ok'] = False
            r['avisos'].append('GCAL_ERROR — no se pudo consultar freebusy en Google Calendar')

        # 4. Caché local
        busy_local = obtener_busy_intervalos_local(host, inicio_utc, fin_utc)

        # 5. Eventos fantasma: local dice ocupado, GCal dice libre
        for loc_ini, loc_fin in busy_local:
            dur_h = (loc_fin - loc_ini).total_seconds() / 3600
            if dur_h < MIN_DURACION_FANTASMA_H:
                continue
            if not _solapa(loc_ini, loc_fin, busy_gcal):
                r['problemas'].append(
                    f'EVENTO_FANTASMA — {loc_ini.strftime("%m-%d %H:%M")}→{loc_fin.strftime("%m-%d %H:%M")} UTC '
                    f'({dur_h:.1f}h) está en caché local pero GCal lo marca como libre (posiblemente cancelado)'
                )

        # 6. Análisis por event type
        event_types = EventType.objects.filter(host=host, activo=True).order_by('id')
        for et in event_types:
            et_r = self._analizar_event_type(et, host, fecha_desde, fecha_hasta, busy_gcal, busy_local, inicio_utc, fin_utc)
            r['total_slots'] += et_r['slots']
            r['event_types'].append(et_r)

        return r

    def _analizar_event_type(self, et, host, fecha_desde, fecha_hasta, busy_gcal, busy_local, inicio_utc=None, fin_utc=None):
        from calendario.event_types.models import EventTypeXHost
        from calendario.bookings.services import _calcular_slots_para_host
        et_r = {'id': et.id, 'nombre': et.nombre, 'slots': 0, 'problemas': [], 'es_pool': False}

        es_pool = EventTypeXHost.objects.filter(event_type=et).exists()
        et_r['es_pool'] = es_pool

        # Slots que calcula la app (usando caché local)
        slots_app = set(calcular_slots(et, fecha_desde, fecha_hasta))
        et_r['slots'] = len(slots_app)

        # Para pool no podemos comparar 1:1 porque los slots vienen de múltiples
        # hosts — el análisis por diferencia no es aplicable.
        if es_pool:
            return et_r

        # Detectar duplicados exactos y solapamientos naturales por separado.
        # - Duplicados: el mismo evento sincronizado dos veces → problema real en caché
        # - Solapamiento natural: dos clases distintas que se pisan → freebusy las fusiona
        #   y desplaza el grid, haciendo la comparación de slots no fiable
        duplicados, hay_solapamiento_natural = _analizar_solapamientos(busy_local)
        if duplicados:
            for d in duplicados[:3]:
                et_r['problemas'].append(
                    f'EVENTO_DUPLICADO — {d[0].strftime("%m-%d %H:%M")}→{d[1].strftime("%m-%d %H:%M")} UTC '
                    f'hay dos eventos distintos en GCal con el mismo horario (revisar calendario del host)'
                )
            if len(duplicados) > 3:
                et_r['problemas'].append(f'  ... y {len(duplicados) - 3} duplicados más')
        if hay_solapamiento_natural:
            from zoneinfo import ZoneInfo
            from calendario.google_calendar.models import GoogleCalendarEvento
            tz_host = ZoneInfo(host.timezone)

            # Mapa (inicio_utc, fin_utc) → es_todo_el_dia para etiquetar cada evento
            todo_el_dia = {
                (e.inicio_utc, e.fin_utc): e.es_todo_el_dia
                for e in GoogleCalendarEvento.objects.filter(
                    host=host, transparencia='opaque',
                    inicio_utc__lt=fin_utc, fin_utc__gt=inicio_utc,
                ).exclude(estado='cancelled').only('inicio_utc', 'fin_utc', 'es_todo_el_dia')
            }

            def _fmt(iv):
                etiqueta = ' [día completo]' if todo_el_dia.get(iv) else ''
                ini_local = iv[0].astimezone(tz_host)
                fin_local = iv[1].astimezone(tz_host)
                return f'{ini_local.strftime("%m-%d %H:%M")}→{fin_local.strftime("%H:%M")} (hora {host.timezone}){etiqueta}'

            pares = []
            sorted_ivs = sorted(busy_local)
            for i in range(len(sorted_ivs) - 1):
                a, b = sorted_ivs[i], sorted_ivs[i + 1]
                if b[0] < a[1] and a != b:
                    pares.append((a, b))

            aviso = 'SOLAPAMIENTO_GCAL — eventos que se pisan en el calendario (comparación de slots omitida):'
            for a, b in pares[:3]:
                aviso += f'\n            · {_fmt(a)}  solapa con  {_fmt(b)}'
            if len(pares) > 3:
                aviso += f'\n            · ... y {len(pares) - 3} solapamientos más'
            et_r.setdefault('avisos', []).append(aviso)
            return et_r

        # Slots que DEBERÍAN existir según GCal + config del host
        slots_gcal = set(_calcular_slots_para_host(et, host, fecha_desde, fecha_hasta, busy_override=busy_gcal))

        # GCal dice libre pero app no ofrece → caché local tiene algo bloqueando de más
        perdidos = sorted(slots_gcal - slots_app)
        if perdidos:
            for s in perdidos[:3]:
                et_r['problemas'].append(
                    f'BLOQUEADO_INCORRECTAMENTE — {s.strftime("%m-%d %H:%M UTC")} '
                    f'GCal dice libre pero la app no lo ofrece (posible evento fantasma en caché)'
                )
            if len(perdidos) > 3:
                et_r['problemas'].append(f'  ... y {len(perdidos) - 3} slots más bloqueados sin razón')

        # App ofrece pero GCal dice busy → caché le falta un evento
        extra = sorted(slots_app - slots_gcal)
        if extra:
            for s in extra[:3]:
                et_r['problemas'].append(
                    f'SLOT_OCUPADO — {s.strftime("%m-%d %H:%M UTC")} '
                    f'ofrecido por la app pero GCal dice busy (falta evento en caché)'
                )
            if len(extra) > 3:
                et_r['problemas'].append(f'  ... y {len(extra) - 3} slots más en conflicto')

        return et_r

    # ------------------------------------------------------------------
    # Salida en terminal
    # ------------------------------------------------------------------

    def _imprimir_resultado(self, r):
        email = r['email']
        problemas = r['problemas'] + [p for et in r['event_types'] for p in et['problemas']]
        avisos = r['avisos'] + [a for et in r['event_types'] for a in et.get('avisos', [])]

        if problemas:
            icono = self.style.ERROR('❌')
        elif avisos:
            icono = self.style.WARNING('⚠️')
        else:
            icono = self.style.SUCCESS('✅')

        slots_info = f"{r['total_slots']} slots"
        self.stdout.write(f'\n{icono}  {email}  ({slots_info})')

        for et in r['event_types']:
            et_avisos = et.get('avisos', [])
            if et['problemas']:
                estado = '  ✗'
            elif et_avisos:
                estado = '  ⚠'
            else:
                estado = '  ·'
            self.stdout.write(f"     {estado} [ID {et['id']}] {et['nombre']} — {et['slots']} slots")
            for p in et['problemas']:
                self.stdout.write(self.style.ERROR(f'          {p}'))
            for a in et_avisos:
                self.stdout.write(self.style.WARNING(f'          {a}'))

        for a in r['avisos']:
            self.stdout.write(self.style.WARNING(f'     ⚠  {a}'))
        for p in r['problemas']:
            self.stdout.write(self.style.ERROR(f'     ✗  {p}'))


# ------------------------------------------------------------------
# Generación del archivo .md
# ------------------------------------------------------------------

def _generar_md(resultados, hoy, dias):
    ok, con_avisos, con_problemas = [], [], []
    for r in resultados:
        todos_problemas = r['problemas'] + [p for et in r['event_types'] for p in et['problemas']]
        todos_avisos = r['avisos'] + [a for et in r['event_types'] for a in et.get('avisos', [])]
        if todos_problemas:
            con_problemas.append(r)
        elif todos_avisos:
            con_avisos.append(r)
        else:
            ok.append(r)

    lines = [
        f'# Diagnóstico de disponibilidad — {hoy}',
        f'',
        f'Período analizado: **{hoy}** → **{hoy + datetime.timedelta(days=dias)}** ({dias} días)',
        f'',
        f'| Estado | Hosts |',
        f'|--------|-------|',
        f'| ✅ Sin problemas | {len(ok)} |',
        f'| ⚠️ Avisos | {len(con_avisos)} |',
        f'| ❌ Problemas | {len(con_problemas)} |',
        f'',
    ]

    if con_problemas:
        lines += ['## ❌ Hosts con problemas', '']
        for r in con_problemas:
            lines.append(f'### {r["email"]}')
            lines.append(f'Slots totales en el período: **{r["total_slots"]}**')
            lines.append('')
            todos_prob = r['problemas'] + [p for et in r['event_types'] for p in et['problemas']]
            for p in todos_prob:
                lines.append(f'- ❌ {p}')
            lines.append('')
            lines.append('**Event types:**')
            for et in r['event_types']:
                pool_tag = ' *(pool)*' if et.get('es_pool') else ''
                lines.append(f'- [ID {et["id"]}] {et["nombre"]}{pool_tag} — {et["slots"]} slots')
                for p in et['problemas']:
                    lines.append(f'  - ❌ {p}')
            lines.append('')

    if con_avisos:
        lines += ['## ⚠️ Hosts con avisos', '']
        for r in con_avisos:
            lines.append(f'### {r["email"]}')
            lines.append(f'Slots totales: **{r["total_slots"]}**')
            lines.append('')
            for a in r['avisos']:
                lines.append(f'- ⚠️ {a}')
            lines.append('')
            lines.append('**Event types:**')
            for et in r['event_types']:
                pool_tag = ' *(pool)*' if et.get('es_pool') else ''
                lines.append(f'- [ID {et["id"]}] {et["nombre"]}{pool_tag} — {et["slots"]} slots')
            lines.append('')

    if ok:
        lines += ['## ✅ Hosts sin problemas', '']
        for r in ok:
            et_resumen = ', '.join(f'[{et["id"]}] {et["slots"]}sl' for et in r['event_types'])
            lines.append(f'- **{r["email"]}** — {r["total_slots"]} slots — {et_resumen}')
        lines.append('')

    return '\n'.join(lines)
