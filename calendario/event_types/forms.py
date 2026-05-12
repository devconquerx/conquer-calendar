from django import forms
from django.contrib.auth import get_user_model

from .models import EventType


User = get_user_model()


def _hosts_queryset():
    return (User.objects
            .filter(is_active=True, roles_asignados__rol__nombre='host')
            .distinct()
            .order_by('username'))


class EventTypeForm(forms.ModelForm):
    buffer_antes_minutos = forms.IntegerField(
        required=False, min_value=0, initial=0,
        label='Buffer antes (min)',
    )
    buffer_despues_minutos = forms.IntegerField(
        required=False, min_value=0, initial=0,
        label='Buffer después (min)',
    )
    aviso_minimo_horas = forms.IntegerField(
        required=False, min_value=0, initial=0,
        label='Aviso mínimo (horas)',
    )

    class Meta:
        model = EventType
        fields = [
            'nombre', 'descripcion', 'duracion_minutos',
            'buffer_antes_minutos', 'buffer_despues_minutos',
            'aviso_minimo_horas', 'activo',
        ]
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}

    def clean_buffer_antes_minutos(self):
        v = self.cleaned_data.get('buffer_antes_minutos')
        return v if v is not None else 0

    def clean_buffer_despues_minutos(self):
        v = self.cleaned_data.get('buffer_despues_minutos')
        return v if v is not None else 0

    def clean_aviso_minimo_horas(self):
        v = self.cleaned_data.get('aviso_minimo_horas')
        return v if v is not None else 0
