from django import forms
from django.db import transaction

from .models import Permiso, PermisoXRol, Rol


class RolForm(forms.ModelForm):
    permisos = forms.ModelMultipleChoiceField(
        queryset=Permiso.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Permisos',
    )

    class Meta:
        model = Rol
        fields = ['nombre', 'descripcion']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permisos'].queryset = Permiso.objects.all()
        if self.instance and self.instance.pk:
            self.fields['permisos'].initial = self.instance.permisos.all()

    def save(self, commit=True):
        rol = super().save(commit=commit)
        if commit:
            permisos = self.cleaned_data.get('permisos', [])
            with transaction.atomic():
                PermisoXRol.objects.filter(rol=rol).delete()
                PermisoXRol.objects.bulk_create([
                    PermisoXRol(rol=rol, permiso=p) for p in permisos
                ])
        return rol
