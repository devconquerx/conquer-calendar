from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from .models import EventType


User = get_user_model()


def _hosts_queryset():
    return (User.objects
            .filter(is_active=True, roles_asignados__rol__nombre='host')
            .distinct()
            .order_by('username'))


def _generar_slug_equipo(nombre, exclude_pk=None):
    base = slugify(nombre) or 'evento'
    slug = base
    i = 2
    while True:
        qs = EventType.objects.filter(slug_equipo=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        slug = f'{base}-{i}'
        i += 1


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
    es_equipo = forms.BooleanField(
        required=False,
        label='Evento de equipo',
    )

    class Meta:
        model = EventType
        fields = [
            'nombre', 'descripcion', 'duracion_minutos',
            'buffer_antes_minutos', 'buffer_despues_minutos',
            'aviso_minimo_horas', 'activo',
        ]
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.slug_equipo:
            self.fields['es_equipo'].initial = True

    def clean_buffer_antes_minutos(self):
        v = self.cleaned_data.get('buffer_antes_minutos')
        return v if v is not None else 0

    def clean_buffer_despues_minutos(self):
        v = self.cleaned_data.get('buffer_despues_minutos')
        return v if v is not None else 0

    def clean_aviso_minimo_horas(self):
        v = self.cleaned_data.get('aviso_minimo_horas')
        return v if v is not None else 0
