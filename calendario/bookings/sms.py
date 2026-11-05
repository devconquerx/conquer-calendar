"""
Recordatorios por SMS con LabsMobile, el mismo proveedor que usa el CRM.

Cada recordatorio ocupa como máximo un SMS: 160 caracteres del alfabeto GSM de 7
bits. Por eso no se envía nunca `long` ni `ucs2`, las tildes y los emojis se
limpian antes de enviar (con `ucs2` un SMS bajaría a 70 caracteres), y si un
nombre largo hace que el mensaje no quepa, se recorta ese nombre.

Las reservas se marcan como procesadas antes de llamar al proveedor. Si el envío
se queda a medias preferimos perder un recordatorio a mandar dos: solo se
reintenta cuando sabemos que el SMS no salió.
"""
import logging
import re
import secrets
import string
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q

from .correos import _DIAS_ABREV, _MESES_ABREV, resolver_config

try:
    import phonenumbers
except ImportError:  # Igual que en forms.py: la falta del paquete no debe tumbar el cron.
    phonenumbers = None


logger = logging.getLogger(__name__)

URL_ENVIO = 'https://api.labsmobile.com/json/send'
TIMEOUT_SEGUNDOS = 15
MAX_CARACTERES = 160
MAX_INTENTOS = 5
MAX_POR_EJECUCION = 100
HORAS_POR_DEFECTO = (24, 1)

MENSAJE_POR_DEFECTO = (
    'Hola {{nombre}}, recuerda tu cita {{nombre_evento}} el {{fecha}} a las {{hora}} '
    '({{zona}}). Cambiarla: {{link_reagendar}}'
)

VARIABLES = {
    'nombre': 'Nombre de pila del invitado',
    'nombre_invitado': 'Nombre completo del invitado',
    'nombre_host': 'Nombre del organizador',
    'nombre_evento': 'Nombre del evento',
    'fecha': 'Fecha en la zona del invitado (jue 12 nov)',
    'hora': 'Hora en la zona del invitado (17:00)',
    'zona': 'Ciudad de la zona horaria del invitado',
    'duracion': 'Duración en minutos',
    'google_meet_url': 'Enlace de Google Meet',
    'link_reagendar': 'Enlace corto para cambiar la cita',
    'link_cancelar': 'Enlace corto para cancelar la cita',
}

# Si el mensaje no cabe se recortan, en este orden, los textos de longitud libre.
# Las fechas y los enlaces no se tocan: recortados dejarían de servir.
RECORTABLES = ('nombre_evento', 'nombre_invitado', 'nombre_host', 'zona', 'nombre')
LONGITUD_MINIMA_RECORTE = 8

_LETRAS_CODIGO = string.ascii_letters + string.digits
_LONGITUD_CODIGO = 10
_RE_VARIABLE = re.compile(r'\{\{\s*(\w+)\s*\}\}')

_GSM_BASICO = set(
    '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà'
)
# Estos también caben en un SMS normal, pero cada uno cuenta como dos caracteres.
_GSM_EXTENDIDO = set('^{}\\[~]|€')
_SUSTITUTOS = {
    '“': '"', '”': '"', '„': '"', '‘': "'", '’': "'", '´': "'", '`': "'",
    '–': '-', '—': '-', '−': '-', '…': '...', '•': '-', '·': '-', ' ': ' ',
}


@dataclass
class ResultadoEnvio:
    ok: bool
    id_proveedor: str = ''
    error: str = ''
    # Sabemos que el SMS no salió y puede salir en otra pasada.
    reintentable: bool = False
    # El fallo es de la cuenta (credenciales o saldo): afecta a todas las reservas.
    detener_pasada: bool = False
    respuesta: dict = field(default_factory=dict)


def limpiar_texto(texto):
    """Deja solo caracteres GSM: «Raúl» pasa a «Raul» y los emojis desaparecen."""
    salida = []
    for caracter in (texto or '').replace('\r\n', '\n').replace('\r', '\n'):
        if caracter in _GSM_BASICO or caracter in _GSM_EXTENDIDO:
            salida.append(caracter)
        elif caracter in _SUSTITUTOS:
            salida.append(_SUSTITUTOS[caracter])
        else:
            base = unicodedata.normalize('NFKD', caracter)
            salida.append(''.join(c for c in base if c in _GSM_BASICO or c in _GSM_EXTENDIDO))
    return ''.join(salida)


def longitud_sms(texto):
    return sum(2 if c in _GSM_EXTENDIDO else 1 for c in texto)


def _sustituir(plantilla, valores):
    return _RE_VARIABLE.sub(lambda m: valores.get(m.group(1), m.group(0)), plantilla)


def _recortar_mensaje(plantilla, valores, longitud_minima=LONGITUD_MINIMA_RECORTE):
    valores = {clave: limpiar_texto(valor) for clave, valor in valores.items()}
    plantilla = limpiar_texto(plantilla)
    mensaje = _sustituir(plantilla, valores)
    for clave in RECORTABLES:
        while longitud_sms(mensaje) > MAX_CARACTERES and len(valores.get(clave, '')) > longitud_minima:
            valores[clave] = valores[clave][:-1].rstrip()
            mensaje = _sustituir(plantilla, valores)
    return mensaje.strip()


def componer_mensaje(plantilla, valores):
    """Devuelve un texto que siempre cabe en un SMS."""
    mensaje = _recortar_mensaje(plantilla, valores)
    # La validación del formulario impide llegar aquí; es la última barrera para
    # no pagar nunca dos SMS, por ejemplo con un SITE_URL más largo que el actual.
    while longitud_sms(mensaje) > MAX_CARACTERES:
        mensaje = mensaje[:-1]
    return mensaje


def valores_de_ejemplo():
    sitio = settings.SITE_URL.rstrip('/')
    return {
        'nombre': 'Ana',
        'nombre_invitado': 'Ana Martínez',
        'nombre_host': 'Raúl Pérez',
        'nombre_evento': 'Llamada de admisiones',
        'fecha': 'jue 12 nov',
        'hora': '17:00',
        'zona': 'Madrid',
        'duracion': '30',
        'google_meet_url': 'https://meet.google.com/abc-defg-hij',
        'link_reagendar': f'{sitio}/s/{"x" * _LONGITUD_CODIGO}',
        'link_cancelar': f'{sitio}/s/{"x" * _LONGITUD_CODIGO}/c',
    }


def validar_plantilla(texto):
    """Rechaza variables que no existen y textos que ni recortando caben en un SMS."""
    desconocidas = sorted({v for v in _RE_VARIABLE.findall(texto or '') if v not in VARIABLES})
    if desconocidas:
        raise ValidationError(
            'Estas variables no existen: ' + ', '.join('{{%s}}' % v for v in desconocidas) + '.'
        )
    longitud = longitud_sms(_recortar_mensaje(texto or '', valores_de_ejemplo()))
    if longitud > MAX_CARACTERES:
        raise ValidationError(
            f'No cabe en un SMS: ocupa al menos {longitud} caracteres y el máximo es {MAX_CARACTERES}.'
        )


def normalizar_telefono(valor):
    """Número internacional solo con dígitos, o '' si no sirve para enviar un SMS."""
    digitos = ''.join(c for c in (valor or '') if c.isdigit())
    if not digitos:
        return ''
    if phonenumbers is None:
        return digitos if len(digitos) >= 8 else ''
    try:
        numero = phonenumbers.parse(f'+{digitos}', None)
    except phonenumbers.NumberParseException:
        return ''
    return digitos if phonenumbers.is_valid_number(numero) else ''


def sms_configurado():
    return bool(settings.LABSMOBILE_USERNAME and settings.LABSMOBILE_API_TOKEN)


def enviar_sms(telefono, mensaje):
    payload = {
        'message': mensaje,
        'tpoa': settings.LABSMOBILE_SENDER,
        'recipient': [{'msisdn': telefono}],
    }
    if settings.LABSMOBILE_TEST:
        payload['test'] = '1'

    try:
        respuesta = requests.post(
            URL_ENVIO,
            json=payload,
            auth=(settings.LABSMOBILE_USERNAME, settings.LABSMOBILE_API_TOKEN),
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.exceptions.ConnectTimeout as exc:
        return ResultadoEnvio(False, error=f'Sin conexión con LabsMobile: {exc}', reintentable=True)
    except requests.exceptions.RequestException as exc:
        # Pudo llegar a salir: reintentar podría mandar un segundo SMS.
        return ResultadoEnvio(False, error=f'Respuesta perdida de LabsMobile: {exc}')

    try:
        datos = respuesta.json()
    except ValueError:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    codigo = str(datos.get('code', ''))
    detalle = str(datos.get('message') or respuesta.text[:300])

    # El HTTP 200 no basta: el resultado real del envío viene en `code`.
    if respuesta.status_code == 200 and codigo == '0':
        return ResultadoEnvio(True, id_proveedor=str(datos.get('subid', '')), respuesta=datos)

    error = f'HTTP {respuesta.status_code}, código {codigo or "-"}: {detalle}'
    return ResultadoEnvio(
        False,
        error=error,
        reintentable=respuesta.status_code >= 500 or codigo == '30',
        detener_pasada=respuesta.status_code in (401, 402, 403) or codigo == '35',
        respuesta=datos,
    )
