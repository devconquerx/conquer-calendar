from django import forms


class BookingForm(forms.Form):
    inicio_utc = forms.DateTimeField(
        widget=forms.HiddenInput,
        input_formats=['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z'],
    )
    nombre_invitado = forms.CharField(max_length=150, min_length=2)
    email_invitado = forms.EmailField()
    notas = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def clean_nombre_invitado(self):
        v = self.cleaned_data['nombre_invitado'].strip()
        if len(v) < 2:
            raise forms.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return v
