from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from calendario.users.models import User


class ConquerSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get('email', '').lower().strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(
                request,
                "No tienes acceso a esta aplicación. Contacta a tu administrador.",
            )
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

        if not user.is_active:
            messages.error(
                request,
                "Tu cuenta está desactivada. Contacta a tu administrador.",
            )
            raise ImmediateHttpResponse(redirect(settings.LOGIN_URL))

    def is_auto_signup_allowed(self, request, sociallogin):
        return False
