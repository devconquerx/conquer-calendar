"""Sube a Supabase los leads, prellamadas y reservas de los últimos N días.

Para rellenar las tablas tras cambiar el esquema del respaldo, o tras una caída
larga de Supabase. Es idempotente (upsert por source_id): se puede repetir.
Los requests en crudo de lo pasado no existen: esos solo se capturan al llegar.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from calendario.core import respaldo, supabase


class Command(BaseCommand):
    help = 'Sube a Supabase leads, prellamadas y reservas de los últimos N días.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7)
        parser.add_argument('--lote', type=int, default=500)

    def handle(self, *args, **opts):
        from calendario.bookings.models import Reserva
        from calendario.funnels.models import Prellamada
        from calendario.leads.models import Lead

        desde = timezone.now() - timedelta(days=opts['dias'])
        for Modelo, campo, tabla in (
            (Lead, 'created', settings.SUPABASE_TABLE_LEADS),
            (Prellamada, 'creado_en', settings.SUPABASE_TABLE_PRE_SCHEDULES),
            (Reserva, 'fecha_creacion', settings.SUPABASE_TABLE_SCHEDULES),
        ):
            qs = Modelo.objects.filter(**{f'{campo}__gte': desde}).order_by('pk')
            qs = qs.prefetch_related('tags') if hasattr(Modelo, 'tags') else qs
            lote, total = [], 0
            for obj in qs.iterator(chunk_size=opts['lote']):
                lote.append(respaldo.fila_de_objeto(obj, getattr(obj, campo)))
                if len(lote) >= opts['lote']:
                    supabase.insert_rows(tabla, lote, on_conflict='source_id')
                    total += len(lote)
                    lote = []
            if lote:
                supabase.insert_rows(tabla, lote, on_conflict='source_id')
                total += len(lote)
            self.stdout.write(self.style.SUCCESS(f'{tabla}: {total} filas'))
