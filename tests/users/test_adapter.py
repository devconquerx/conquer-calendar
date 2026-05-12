from unittest.mock import MagicMock, patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import reverse

from allauth.exceptions import ImmediateHttpResponse

from calendario.users.adapters import ConquerSocialAccountAdapter
from tests.factories import EMAIL_HOST, crear_host


def _sociallogin_mock(email):
    sociallogin = MagicMock()
    sociallogin.account.extra_data = {'email': email}
    return sociallogin


def _request_con_mensajes():
    factory = RequestFactory()
    request = factory.get('/')
    request.session = {}
    messages = FallbackStorage(request)
    request._messages = messages
    return request


class AdaptadorGoogleTest(TestCase):

    def setUp(self):
        self.adapter = ConquerSocialAccountAdapter()

    def test_usuario_importado_activo_pasa(self):
        crear_host(email=EMAIL_HOST)
        request = _request_con_mensajes()
        sociallogin = _sociallogin_mock(EMAIL_HOST)

        # No debe lanzar excepción
        try:
            self.adapter.pre_social_login(request, sociallogin)
        except ImmediateHttpResponse:
            self.fail("pre_social_login bloqueó un usuario válido")

    def test_email_no_importado_bloquea(self):
        request = _request_con_mensajes()
        sociallogin = _sociallogin_mock('desconocido@conquerx.com')

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_usuario_inactivo_bloquea(self):
        host = crear_host(email=EMAIL_HOST)
        host.is_active = False
        host.save()

        request = _request_con_mensajes()
        sociallogin = _sociallogin_mock(EMAIL_HOST)

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_email_gmail_no_importado_bloquea(self):
        """Un email personal (no corporativo) que no está importado no puede entrar."""
        request = _request_con_mensajes()
        sociallogin = _sociallogin_mock('santiagocentenot@gmail.com')

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_is_auto_signup_allowed_siempre_false(self):
        request = _request_con_mensajes()
        resultado = self.adapter.is_auto_signup_allowed(request, MagicMock())
        self.assertFalse(resultado)
