from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from calendario.permisos.models import Rol, RolXUsuario
from calendario.users.models import User
from tests.factories import EMAIL_HOST, crear_rol_host


class ImportarHostsCommandTest(TestCase):

    def setUp(self):
        crear_rol_host()

    def _call(self, *args, **kwargs):
        out = StringIO()
        call_command('importar_hosts', *args, stdout=out, **kwargs)
        return out.getvalue()

    def test_importa_un_email(self):
        self._call('--emails', EMAIL_HOST)
        self.assertTrue(User.objects.filter(email=EMAIL_HOST).exists())

    def test_password_inutilizable(self):
        self._call('--emails', EMAIL_HOST)
        user = User.objects.get(email=EMAIL_HOST)
        self.assertFalse(user.has_usable_password())

    def test_usuario_activo(self):
        self._call('--emails', EMAIL_HOST)
        user = User.objects.get(email=EMAIL_HOST)
        self.assertTrue(user.is_active)

    def test_asigna_rol_host(self):
        self._call('--emails', EMAIL_HOST)
        user = User.objects.get(email=EMAIL_HOST)
        tiene_rol = RolXUsuario.objects.filter(usuario=user, rol__nombre='host').exists()
        self.assertTrue(tiene_rol)

    def test_idempotente_no_duplica(self):
        self._call('--emails', EMAIL_HOST)
        self._call('--emails', EMAIL_HOST)
        self.assertEqual(User.objects.filter(email=EMAIL_HOST).count(), 1)

    def test_importa_multiples_emails(self):
        emails = [EMAIL_HOST, 'santiagocentenot@gmail.com']
        self._call('--emails', *emails)
        for email in emails:
            self.assertTrue(User.objects.filter(email=email).exists())

    def test_username_generado_del_email(self):
        self._call('--emails', EMAIL_HOST)
        user = User.objects.get(email=EMAIL_HOST)
        self.assertEqual(user.username, EMAIL_HOST.split('@')[0])

    def test_username_sin_colision(self):
        # Dos emails con el mismo prefijo
        self._call('--emails', 'santiago.tovar@conquerx.com', 'santiago.tovar@conquerlanguages.com')
        usernames = list(User.objects.values_list('username', flat=True))
        self.assertEqual(len(usernames), len(set(usernames)))  # sin duplicados

    def test_falla_sin_rol_host(self):
        from django.core.management.base import CommandError
        Rol.objects.filter(nombre='host').delete()
        with self.assertRaises(CommandError):
            self._call('--emails', EMAIL_HOST)
