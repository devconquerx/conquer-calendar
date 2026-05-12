import zoneinfo

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from calendario.users.models import User
from calendario.permisos.models import Rol, RolXUsuario

TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]

COUNTRY_CHOICES = [
    ('', 'Selecciona un país'),
    ('AR', 'Argentina'),
    ('BO', 'Bolivia'),
    ('BR', 'Brasil'),
    ('CA', 'Canadá'),
    ('CL', 'Chile'),
    ('CN', 'China'),
    ('CO', 'Colombia'),
    ('CR', 'Costa Rica'),
    ('CU', 'Cuba'),
    ('DE', 'Alemania'),
    ('DO', 'República Dominicana'),
    ('EC', 'Ecuador'),
    ('EG', 'Egipto'),
    ('ES', 'España'),
    ('FR', 'Francia'),
    ('GB', 'Reino Unido'),
    ('GT', 'Guatemala'),
    ('HN', 'Honduras'),
    ('IT', 'Italia'),
    ('JP', 'Japón'),
    ('MX', 'México'),
    ('NI', 'Nicaragua'),
    ('NL', 'Países Bajos'),
    ('PA', 'Panamá'),
    ('PE', 'Perú'),
    ('PT', 'Portugal'),
    ('PY', 'Paraguay'),
    ('RU', 'Rusia'),
    ('SV', 'El Salvador'),
    ('TR', 'Turquía'),
    ('US', 'Estados Unidos'),
    ('UY', 'Uruguay'),
    ('VE', 'Venezuela'),
    ('ZA', 'Sudáfrica'),
]


class TimezoneForm(forms.Form):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES, label='Zona horaria')


class MiPerfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'country', 'timezone']
        widgets = {
            'country': forms.Select(choices=COUNTRY_CHOICES),
            'timezone': forms.Select(choices=TIMEZONE_CHOICES),
        }


class UsuarioCreacionForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Roles',
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'timezone', 'avatar_url']
        widgets = {
            'timezone': forms.Select(choices=TIMEZONE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['roles'].queryset = Rol.objects.all()
        self.fields['timezone'].widget.attrs.update({'class': 'form-select form-select-lg'})

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        validate_password(p2)
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.username:
            user.username = self._generar_username(user.email)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            roles = self.cleaned_data.get('roles', [])
            RolXUsuario.objects.bulk_create([
                RolXUsuario(usuario=user, rol=rol) for rol in roles
            ])
        return user

    @staticmethod
    def _generar_username(email):
        base = email.split('@')[0]
        username = base
        i = 2
        while User.objects.filter(username=username).exists():
            username = f'{base}{i}'
            i += 1
        return username


class UsuarioEdicionForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Roles',
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'timezone', 'avatar_url']
        widgets = {
            'timezone': forms.Select(choices=TIMEZONE_CHOICES, attrs={'class': 'form-control form-control-lg'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['roles'].queryset = Rol.objects.all()
        self.fields['timezone'].widget.attrs.update({'class': 'form-select form-select-lg'})
        if self.instance and self.instance.pk:
            self.fields['roles'].initial = Rol.objects.filter(
                asignaciones__usuario=self.instance
            )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            roles = self.cleaned_data.get('roles', [])
            with transaction.atomic():
                RolXUsuario.objects.filter(usuario=user).delete()
                RolXUsuario.objects.bulk_create([
                    RolXUsuario(usuario=user, rol=rol) for rol in roles
                ])
        return user


class CambiarPasswordOtroForm(forms.Form):
    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        validate_password(p2)
        return p2


class CambiarMiPasswordForm(forms.Form):
    password_actual = forms.CharField(
        label='Contraseña actual',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
        strip=False,
    )
    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password_actual(self):
        pwd = self.cleaned_data.get('password_actual')
        if not self.user.check_password(pwd):
            raise forms.ValidationError('Contraseña actual incorrecta.')
        return pwd

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        validate_password(p2, user=self.user)
        return p2
