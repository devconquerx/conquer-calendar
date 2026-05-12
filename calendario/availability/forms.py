from django import forms
from .models import BloqueHorarioSemanal


class BloqueHorarioSemanalForm(forms.ModelForm):
    class Meta:
        model = BloqueHorarioSemanal
        fields = ['dia_semana', 'hora_inicio', 'hora_fin']
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
        }
