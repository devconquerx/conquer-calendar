from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from calendario.bookings.models import ConfigCorreoGrupo, PlantillaCorreo

from .models import Grupo, GrupoXUsuario

User = get_user_model()


def _usuarios_activos_context():
    return [
        {
            'id': u.pk,
            'nombre': u.get_full_name() or u.username,
            'email': u.email,
            'avatar': u.avatar_url or '',
            'iniciales': (
                (u.first_name[:1] + u.last_name[:1]).upper()
                or u.username[:2].upper()
            ),
        }
        for u in User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'email')
    ]


def _supervisores_disponibles_context():
    return [
        {
            'id': u.pk,
            'nombre': u.get_full_name() or u.username,
            'email': u.email,
            'avatar': u.avatar_url or '',
            'iniciales': (
                (u.first_name[:1] + u.last_name[:1]).upper()
                or u.username[:2].upper()
            ),
        }
        for u in User.objects.filter(
            is_active=True,
            roles_asignados__rol__nombre='supervisor',
        ).distinct().order_by('first_name', 'last_name', 'email')
    ]


class GrupoForm(forms.ModelForm):
    # Non-model fields — IDs come as hidden inputs from the JS picker
    supervisores_ids = forms.CharField(required=False, widget=forms.HiddenInput)
    miembros_ids = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Grupo
        fields = ['nombre', 'descripcion']

    def _parse_ids(self, field_name):
        raw = self.data.getlist(field_name)
        ids = []
        for v in raw:
            try:
                ids.append(int(v))
            except (ValueError, TypeError):
                pass
        return ids

    def clean(self):
        cleaned = super().clean()
        self._supervisor_ids = self._parse_ids('supervisores')
        self._miembro_ids = self._parse_ids('miembros')

        if not self._supervisor_ids:
            raise forms.ValidationError({'supervisores_ids': 'Un grupo debe tener al menos un supervisor.'})

        # Ensure supervisors exist with supervisor role
        supervisores_qs = User.objects.filter(
            pk__in=self._supervisor_ids,
            is_active=True,
            roles_asignados__rol__nombre='supervisor',
        )
        if supervisores_qs.count() != len(self._supervisor_ids):
            raise forms.ValidationError({'supervisores_ids': 'Uno o más supervisores seleccionados no son válidos.'})

        return cleaned

    def save(self, commit=True):
        grupo = super().save(commit=commit)
        if commit:
            supervisor_ids = set(self._supervisor_ids)
            miembro_ids = set(self._miembro_ids) | supervisor_ids  # supervisor ⊆ miembros
            with transaction.atomic():
                GrupoXUsuario.objects.filter(grupo=grupo).delete()
                GrupoXUsuario.objects.bulk_create([
                    GrupoXUsuario(grupo=grupo, usuario_id=uid, es_supervisor=(uid in supervisor_ids))
                    for uid in miembro_ids
                ])
        return grupo

    def initial_supervisor_ids(self):
        if self.instance and self.instance.pk:
            return list(self.instance.supervisores.values_list('pk', flat=True))
        return []

    def initial_miembro_ids(self):
        if self.instance and self.instance.pk:
            return list(
                GrupoXUsuario.objects.filter(grupo=self.instance, es_supervisor=False)
                .values_list('usuario_id', flat=True)
            )
        return []


class GrupoMiembrosForm(forms.Form):
    """Formulario reducido para que supervisores editen solo los miembros (no supervisores)."""

    def __init__(self, *args, grupo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.grupo = grupo

    def _parse_ids(self):
        ids = []
        for v in self.data.getlist('miembros'):
            try:
                ids.append(int(v))
            except (ValueError, TypeError):
                pass
        return ids

    def save(self):
        miembro_ids = set(self._parse_ids())
        with transaction.atomic():
            GrupoXUsuario.objects.filter(grupo=self.grupo, es_supervisor=False).delete()
            GrupoXUsuario.objects.bulk_create([
                GrupoXUsuario(grupo=self.grupo, usuario_id=uid, es_supervisor=False)
                for uid in miembro_ids
            ])
        return self.grupo

    def initial_miembro_ids(self):
        return list(
            GrupoXUsuario.objects.filter(grupo=self.grupo, es_supervisor=False)
            .values_list('usuario_id', flat=True)
        )


_PERMISOS_FIELDS = [
    'permite_ver_reservas_grupo',
    'bloquear_editar_disponibilidad',
    'bloquear_crear_event_types',
    'bloquear_editar_event_types',
    'bloquear_activar_event_types',
    'bloquear_eliminar_event_types',
    'bloquear_cancelar_reservas',
]


class GrupoPermisosForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = _PERMISOS_FIELDS
        widgets = {
            f: forms.CheckboxInput(attrs={'class': 'form-check-input form-check-input-lg'})
            for f in _PERMISOS_FIELDS
        }


_PLANTILLA_WIDGET = forms.Select(attrs={'class': 'form-select form-select-solid'})

_PLANTILLA_QUERYSET = PlantillaCorreo.objects.filter(activa=True).order_by('nombre')


class ConfigCorreoGrupoForm(forms.ModelForm):
    plantilla_confirmacion_host = forms.ModelChoiceField(
        queryset=_PLANTILLA_QUERYSET,
        required=False,
        empty_label='— Sin plantilla (usa global) —',
        widget=_PLANTILLA_WIDGET,
        label='Correo al host',
        help_text='Sin plantilla, aplica la configuración global.',
    )
    plantilla_confirmacion_inv = forms.ModelChoiceField(
        queryset=_PLANTILLA_QUERYSET,
        required=False,
        empty_label='— Sin plantilla (usa global) —',
        widget=_PLANTILLA_WIDGET,
        label='Correo al invitado',
    )
    plantilla_recordatorio = forms.ModelChoiceField(
        queryset=_PLANTILLA_QUERYSET,
        required=False,
        empty_label='— Sin plantilla (usa global) —',
        widget=_PLANTILLA_WIDGET,
        label='Plantilla de recordatorio',
    )

    class Meta:
        model = ConfigCorreoGrupo
        fields = ['plantilla_confirmacion_host', 'plantilla_confirmacion_inv', 'plantilla_recordatorio']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            return
        try:
            from calendario.bookings.models import ConfigCorreoDefault
            cfg = ConfigCorreoDefault.get()
            if not self.initial.get('plantilla_confirmacion_host'):
                self.initial['plantilla_confirmacion_host'] = cfg.plantilla_confirmacion_host_id
            if not self.initial.get('plantilla_confirmacion_inv'):
                self.initial['plantilla_confirmacion_inv'] = cfg.plantilla_confirmacion_inv_id
            if not self.initial.get('plantilla_recordatorio'):
                self.initial['plantilla_recordatorio'] = cfg.plantilla_recordatorio_id
        except Exception:
            pass
