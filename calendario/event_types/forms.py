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
    # El checkbox del formulario; el modelo guarda el modo como texto para que se
    # pueda ampliar más adelante sin migrar datos.
    rango_por_fechas = forms.BooleanField(
        required=False,
        label='Usar un rango de fechas concreto',
    )
    rango_fecha_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Reservable desde',
    )
    rango_fecha_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Reservable hasta',
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
            'aviso_minimo_minutos', 'aviso_maximo_dias',
            'rango_fecha_inicio', 'rango_fecha_fin', 'activo', 'acceso',
            'crm_destino', 'unico_por_invitado', 'mostrar_caja_comentarios',
            'confirmacion_tipo', 'confirmacion_url',
            'gcal_palabras_ignorar',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'gcal_palabras_ignorar': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'crm_destino': 'Destino en el CRM',
            'unico_por_invitado': 'Solo una reserva por invitado',
            'mostrar_caja_comentarios': 'Caja de comentarios',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hosts'].queryset = _hosts_queryset()
        # Igual que los buffers y los avisos: no todas las vistas del panel
        # reenvían el formulario entero, y un campo obligatorio de más rompe el
        # guardado desde las que mandan solo un subconjunto.
        self.fields['acceso'].required = False
        if self.instance.pk and not self.is_bound:
            self.fields['rango_por_fechas'].initial = (
                self.instance.rango_tipo == EventType.RANGO_FECHAS
            )
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

    def clean_acceso(self):
        """Si el POST no lo trae, se conserva lo que el evento ya tenía.

        Abrir o cerrar un evento a los alumnos tiene que ser siempre una
        decisión explícita: un guardado desde otra pantalla no puede cambiarlo
        de rebote en ningún sentido.
        """
        v = self.cleaned_data.get('acceso')
        return v or self.instance.acceso or EventType.ACCESO_PUBLICO

    def clean(self):
        """Traduce el checkbox del formulario al modo que guarda el modelo.

        Las fechas se conservan aunque se desmarque el checkbox: el modo lo decide
        `rango_tipo`, así que quedan guardadas sin efecto y volver a marcarlo no
        obliga a escribirlas otra vez.
        """
        cleaned = super().clean()
        usa_fechas = bool(cleaned.get('rango_por_fechas'))
        self.instance.rango_tipo = (
            EventType.RANGO_FECHAS if usa_fechas else EventType.RANGO_ROLLING
        )
        if not usa_fechas:
            return cleaned

        inicio = cleaned.get('rango_fecha_inicio')
        fin = cleaned.get('rango_fecha_fin')
        if not inicio:
            self.add_error('rango_fecha_inicio', 'Indica desde qué día se puede reservar.')
        if not fin:
            self.add_error('rango_fecha_fin', 'Indica hasta qué día se puede reservar.')
        if inicio and fin and fin < inicio:
            self.add_error('rango_fecha_fin', 'La fecha final no puede ser anterior a la inicial.')
        return cleaned
