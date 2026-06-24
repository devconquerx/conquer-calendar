from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from .models import EventType, EventTypeXHost


User = get_user_model()


def _hosts_queryset():
    return (User.objects
            .filter(is_active=True, roles_asignados__rol__nombre='host')
            .distinct()
            .order_by('first_name', 'username'))


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
    incremento_inicio_minutos = forms.TypedChoiceField(
        coerce=int,
        choices=EventType.INCREMENTO_CHOICES,
        initial=30,
        label='Incremento de inicio',
    )
    buffer_antes_minutos = forms.IntegerField(
        required=False, min_value=0, initial=0,
        label='Buffer antes (min)',
    )
    buffer_despues_minutos = forms.IntegerField(
        required=False, min_value=0, initial=0,
        label='Buffer después (min)',
    )
    aviso_minimo_minutos = forms.TypedChoiceField(
        coerce=int,
        choices=EventType.AVISO_MINIMO_CHOICES,
        initial=0,
        label='Aviso mínimo',
    )
    aviso_maximo_dias = forms.IntegerField(
        required=False, min_value=1, max_value=365, initial=60,
        label='Rango máximo (días)',
    )
    es_equipo = forms.BooleanField(
        required=False,
        label='Evento de equipo',
    )
    hosts = forms.ModelMultipleChoiceField(
        queryset=_hosts_queryset(),
        required=False,
        widget=forms.MultipleHiddenInput,
        label='Organizadores',
    )

    class Meta:
        model = EventType
        fields = [
            'nombre', 'descripcion', 'duracion_minutos',
            'incremento_inicio_minutos',
            'buffer_antes_minutos', 'buffer_despues_minutos',
            'aviso_minimo_minutos', 'aviso_maximo_dias', 'activo',
            'crm_destino', 'unico_por_invitado',
            'confirmacion_tipo', 'confirmacion_url',
        ]
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}
        labels = {
            'crm_destino': 'Destino en el CRM',
            'unico_por_invitado': 'Solo una reserva por invitado',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hosts'].queryset = _hosts_queryset()
        if self.instance.pk and self.instance.slug_equipo:
            self.fields['es_equipo'].initial = True
            if not self.is_bound:
                self.fields['hosts'].initial = list(
                    EventTypeXHost.objects
                    .filter(event_type=self.instance)
                    .values_list('host_id', flat=True)
                )

    def clean_buffer_antes_minutos(self):
        v = self.cleaned_data.get('buffer_antes_minutos')
        return v if v is not None else 0

    def clean_buffer_despues_minutos(self):
        v = self.cleaned_data.get('buffer_despues_minutos')
        return v if v is not None else 0

    def clean_aviso_minimo_minutos(self):
        v = self.cleaned_data.get('aviso_minimo_minutos')
        return v if v is not None else 0

    def clean_aviso_maximo_dias(self):
        v = self.cleaned_data.get('aviso_maximo_dias')
        return v if v is not None else 60
