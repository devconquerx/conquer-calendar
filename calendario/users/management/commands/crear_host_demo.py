from datetime import time

from django.core.management.base import BaseCommand

from calendario.users.models import User
from calendario.permisos.models import Rol, RolXUsuario
from calendario.event_types.models import EventType, EventTypeXHost
from calendario.availability.models import BloqueHorarioSemanal


class Command(BaseCommand):
    help = 'Crea un usuario host de demo y le asigna el rol host'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='host_demo')
        parser.add_argument('--email', default='host@conquer.local')
        parser.add_argument('--password', default='host1234')

    def handle(self, *args, **opts):
        user, created = User.objects.get_or_create(
            username=opts['username'],
            defaults={'email': opts['email'], 'first_name': 'Host', 'last_name': 'Demo'},
        )
        user.email = opts['email']
        user.set_password(opts['password'])
        user.is_active = True
        user.save()

        rol_host = Rol.objects.get(nombre='host')
        RolXUsuario.objects.get_or_create(usuario=user, rol=rol_host)

        verbo = 'Creado' if created else 'Actualizado'
        self.stdout.write(self.style.SUCCESS(
            f'{verbo} {user.username} (rol host). '
            f'Login: {user.email} / {opts["password"]}'
        ))

        et, et_creado = EventType.objects.update_or_create(
            host=user,
            nombre='Demo 30 min',
            defaults={
                'descripcion': 'Sesión de demostración rápida.',
                'duracion_minutos': 30,
                'buffer_antes_minutos': 0,
                'buffer_despues_minutos': 5,
                'aviso_minimo_minutos': 60,
                'precio': None,
                'activo': True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"  · Event type 'Demo 30 min': {'creado' if et_creado else 'ya existía'}."
        ))

        et_demo30 = EventType.objects.filter(nombre='Demo 30 min').order_by('id').first()
        if et_demo30:
            _, pivot_creado = EventTypeXHost.objects.get_or_create(
                event_type=et_demo30, host=user,
            )
            if pivot_creado:
                self.stdout.write(self.style.SUCCESS(
                    f"  · Añadido al pool de '{et_demo30.nombre}' (owner={et_demo30.host.username})."
                ))

        et2, et2_creado = EventType.objects.update_or_create(
            host=user,
            nombre='Demo 60 min',
            defaults={
                'descripcion': 'Sesión más larga para discusión técnica.',
                'duracion_minutos': 60,
                'buffer_antes_minutos': 5,
                'buffer_despues_minutos': 10,
                'aviso_minimo_minutos': 120,
                'precio': 50.00,
                'activo': True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"  · Event type 'Demo 60 min': {'creado' if et2_creado else 'ya existía'}."
        ))
        # user.slug se autopobla en User.save() via slugify(username)
        self.stdout.write(self.style.SUCCESS(
            f"  · Slug usuario: {user.slug}, slug demo-30: {et.slug}, slug demo-60: {et2.slug}"
        ))

        bloques_creados = 0
        for dia in range(5):  # lunes a viernes (0–4)
            for inicio, fin in [(time(9, 0), time(13, 0)), (time(15, 0), time(18, 0))]:
                _, creado = BloqueHorarioSemanal.objects.get_or_create(
                    host=user, dia_semana=dia, hora_inicio=inicio, hora_fin=fin,
                )
                if creado:
                    bloques_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"  · Bloques horarios añadidos: {bloques_creados} (esperados 10 si BD vacía)."
        ))
