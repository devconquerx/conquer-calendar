import logging

from django import forms

logger = logging.getLogger(__name__)

# Validación estricta de teléfono, la misma que hace el funnel con
# libphonenumber-js: no basta con la longitud, el prefijo nacional tiene que
# existir de verdad en ese país. Si el paquete no está instalado (imagen sin
# rebuildear) se sigue exigiendo el campo, pero sin el chequeo estricto: es
# preferible a tumbar la página de reserva entera.
try:
    import phonenumbers
except ImportError:  # pragma: no cover
    phonenumbers = None
    logger.warning(
        "phonenumbers no está instalado: el teléfono de las reservas no se valida "
        "en servidor. Rebuildea la imagen para que vuelva a validarse."
    )


def telefono_valido(valor):
    """¿`valor` (E.164, ej. '+58 4121234567') es un número real de su país?"""
    if phonenumbers is None:
        return True
    try:
        return phonenumbers.is_valid_number(phonenumbers.parse(valor, None))
    except phonenumbers.NumberParseException:
        return False


class BookingForm(forms.Form):
    inicio_utc = forms.DateTimeField(
        widget=forms.HiddenInput,
        input_formats=['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z'],
    )
    nombre_invitado = forms.CharField(max_length=150, min_length=2)
    email_invitado = forms.EmailField()
    telefono_invitado = forms.CharField(max_length=50)
    notas = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    # Sin max_length a propósito: la página mete aquí `window.location.href` al
    # enviar, y una URL con mucho parámetro de anuncio dentro puede pasarse de
    # los 1.500 de la columna. Rechazar la reserva por eso sería absurdo —el
    # tracking es un dato de marketing—, así que se recorta en `clean_url`.
    # Misma decisión que `_tracking_kwargs` en services.py (ver FUNNELS-67).
    url = forms.CharField(required=False, widget=forms.HiddenInput)
    # pre_email del setter que generó el link directo de reagendamiento (viaja
    # como query param en la página, round-tripea por este hidden). Mismo
    # mecanismo que event_id/journey_id en el flujo del funnel — snapshot en
    # Reserva.setter vía RESERVA_TRACKING_FIELDS.
    setter = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_url(self):
        return self._recortar('url')

    def clean_setter(self):
        return self._recortar('setter')

    def _recortar(self, campo):
        """Recorta un campo de tracking al tope de su columna en Reserva."""
        from calendario.bookings.models import Reserva
        valor = self.cleaned_data.get(campo) or ''
        tope = Reserva._meta.get_field(campo).max_length
        return valor[:tope] if tope else valor

    def clean_nombre_invitado(self):
        v = self.cleaned_data['nombre_invitado'].strip()
        if len(v) < 2:
            raise forms.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return v

    def clean_telefono_invitado(self):
        v = self.cleaned_data.get('telefono_invitado', '').strip()
        if not v:
            raise forms.ValidationError("El número de teléfono es obligatorio.")
        if not telefono_valido(v):
            raise forms.ValidationError(
                "Ese número no parece válido. Revisa el país y los dígitos."
            )
        return v
