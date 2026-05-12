import csv

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from calendario.users.models import User
from calendario.permisos.models import Rol, RolXUsuario


class Command(BaseCommand):
    help = (
        'Importa hosts (closers/setters) como usuarios con contraseña inutilizable.\n'
        'Modos:\n'
        '  --dominio conquerx.com --admin admin@conquerx.com  (trae todos desde Workspace)\n'
        '  --emails a@x.com b@x.com                          (lista manual)\n'
        '  --csv hosts.csv                                    (CSV con columnas email, first_name, last_name)'
    )

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument(
            '--dominio',
            metavar='DOMINIO',
            help='Trae todos los usuarios activos del dominio Workspace vía Directory API.',
        )
        grupo.add_argument(
            '--emails',
            nargs='+',
            metavar='EMAIL',
            help='Uno o más emails separados por espacio.',
        )
        grupo.add_argument(
            '--csv',
            dest='csv_path',
            metavar='ARCHIVO',
            help='CSV con columnas: email, first_name (opcional), last_name (opcional).',
        )
        parser.add_argument(
            '--admin',
            metavar='EMAIL_ADMIN',
            help='Email del super-admin a impersonar para llamar a Directory API (requerido con --dominio).',
        )

    def handle(self, *args, **opts):
        try:
            rol_host = Rol.objects.get(nombre='host')
        except Rol.DoesNotExist:
            raise CommandError("El rol 'host' no existe. ¿Corriste las fixtures de roles?")

        registros = self._cargar_registros(opts)
        creados = actualizados = 0

        for email, first_name, last_name in registros:
            email = email.strip().lower()
            if not email:
                continue

            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': self._username_unico(email),
                        'first_name': first_name,
                        'last_name': last_name,
                        'is_active': True,
                    },
                )

                if created:
                    user.set_unusable_password()
                    user.save(update_fields=['password'])
                    creados += 1
                    verbo = self.style.SUCCESS('CREADO   ')
                else:
                    actualizados += 1
                    verbo = self.style.WARNING('YA EXISTE')

                RolXUsuario.objects.get_or_create(usuario=user, rol=rol_host)

            nombre_display = user.get_full_name() or user.username
            self.stdout.write(f'  {verbo}  {email}  ({nombre_display})')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Listo. Creados: {creados}  |  Ya existían: {actualizados}'
        ))

    def _cargar_registros(self, opts):
        if opts['dominio']:
            return self._desde_workspace(opts['dominio'], opts.get('admin'))

        if opts['emails']:
            return [(e, '', '') for e in opts['emails']]

        csv_path = opts['csv_path']
        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                filas = list(reader)
        except FileNotFoundError:
            raise CommandError(f"No se encontró el archivo: {csv_path}")

        registros = []
        for fila in filas:
            email = fila.get('email', '').strip()
            if not email:
                continue
            registros.append((
                email,
                fila.get('first_name', '').strip(),
                fila.get('last_name', '').strip(),
            ))
        return registros

    def _desde_workspace(self, dominio, admin_email):
        if not admin_email:
            raise CommandError(
                '--admin es requerido con --dominio. '
                'Ejemplo: --admin admin@conquerx.com'
            )

        sa_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        if not sa_file:
            raise CommandError(
                'GOOGLE_SERVICE_ACCOUNT_FILE no está configurado en settings.'
            )

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            raise CommandError(
                'Falta google-api-python-client. Instálalo con: pip install google-api-python-client'
            )

        self.stdout.write(f'Conectando a Workspace Directory API como {admin_email}...')

        creds = service_account.Credentials.from_service_account_file(
            sa_file,
            scopes=['https://www.googleapis.com/auth/admin.directory.user.readonly'],
        ).with_subject(admin_email)

        service = build('admin', 'directory_v1', credentials=creds, cache_discovery=False)

        registros = []
        page_token = None

        while True:
            resp = service.users().list(
                domain=dominio,
                maxResults=500,
                orderBy='email',
                pageToken=page_token,
                query='isSuspended=false',
            ).execute()

            for usuario in resp.get('users', []):
                email = usuario.get('primaryEmail', '')
                nombre = usuario.get('name', {})
                first_name = nombre.get('givenName', '')
                last_name = nombre.get('familyName', '')
                registros.append((email, first_name, last_name))

            page_token = resp.get('nextPageToken')
            if not page_token:
                break

        self.stdout.write(f'  {len(registros)} usuarios encontrados en @{dominio}.\n')
        return registros

    @staticmethod
    def _username_unico(email):
        base = email.split('@')[0]
        username = base
        i = 2
        while User.objects.filter(username=username).exists():
            username = f'{base}{i}'
            i += 1
        return username
