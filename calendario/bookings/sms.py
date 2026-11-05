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


def _zona_legible(nombre_zona):
    return nombre_zona.rsplit('/', 1)[-1].replace('_', ' ')


def _asegurar_codigo(reserva):
    from .models import Reserva

    if not reserva.sms_codigo:
        codigo = ''.join(secrets.choice(_LETRAS_CODIGO) for _ in range(_LONGITUD_CODIGO))
        Reserva.objects.filter(pk=reserva.pk).update(sms_codigo=codigo)
        reserva.sms_codigo = codigo
    return reserva.sms_codigo


def _valores_reserva(reserva, plantilla):
    nombre_zona = reserva.timezone_invitado or reserva.host.timezone
    try:
        zona = ZoneInfo(nombre_zona)
    except Exception:
        nombre_zona, zona = 'UTC', ZoneInfo('UTC')
    inicio = reserva.inicio_utc.astimezone(zona)
    partes_nombre = (reserva.nombre_invitado or '').split()
    valores = {
        'nombre': partes_nombre[0] if partes_nombre else '',
        'nombre_invitado': reserva.nombre_invitado or '',
        'nombre_host': reserva.host.get_full_name() or reserva.host.username,
        'nombre_evento': reserva.event_type.nombre,
        'fecha': f'{_DIAS_ABREV[inicio.weekday()].lower()} {inicio.day} {_MESES_ABREV[inicio.month - 1]}',
        'hora': f'{inicio.hour}:{inicio.minute:02d}',
        'zona': _zona_legible(nombre_zona),
        'duracion': str(reserva.event_type.duracion_minutos),
        'google_meet_url': reserva.google_meet_url or '',
    }
    # El código corto solo se crea si el mensaje va a usarlo.
    usadas = set(_RE_VARIABLE.findall(plantilla))
    if usadas & {'link_reagendar', 'link_cancelar'}:
        sitio = settings.SITE_URL.rstrip('/')
        codigo = _asegurar_codigo(reserva)
        valores['link_reagendar'] = f'{sitio}/s/{codigo}'
        valores['link_cancelar'] = f'{sitio}/s/{codigo}/c'
    return valores


def mensaje_de_reserva(reserva):
    plantilla = (reserva.event_type.sms_mensaje or '').strip() or MENSAJE_POR_DEFECTO
    return componer_mensaje(plantilla, _valores_reserva(reserva, plantilla))


def horas_de_recordatorio(reserva):
    """Lista de (número de recordatorio, horas antes) activos para la reserva."""
    event_type = reserva.event_type
    if event_type.sms_usar_horas_correo:
        plantilla, _ = resolver_config(reserva, 'recordatorio')
        if not plantilla:
            return list(enumerate(HORAS_POR_DEFECTO, start=1))
        return [
            (n, getattr(plantilla, f'recordatorio_{n}_horas'))
            for n in (1, 2)
            if getattr(plantilla, f'recordatorio_{n}_activo')
        ]
    return [
        (n, horas)
        for n, horas in (
            (1, event_type.sms_recordatorio_1_horas),
            (2, event_type.sms_recordatorio_2_horas),
        )
        if horas
    ]


def _reclamar(reserva, n):
    """Marca el recordatorio como procesado. Solo gana una ejecución del cron."""
    from .models import Reserva

    campo = f'sms_recordatorio_{n}_procesado'
    return bool(Reserva.objects.filter(pk=reserva.pk, **{campo: False}).update(**{campo: True}))


def _devolver(reserva, n, sumar_intento):
    from django.db.models import F

    from .models import Reserva

    cambios = {f'sms_recordatorio_{n}_procesado': False}
    if sumar_intento:
        cambios[f'sms_recordatorio_{n}_intentos'] = F(f'sms_recordatorio_{n}_intentos') + 1
    Reserva.objects.filter(pk=reserva.pk).update(**cambios)


def _pendientes_ahora(reserva, ahora):
    """Recordatorios que tocan ya, del más cercano a la cita al más lejano.

    Si la reserva se creó con la ventana ya abierta, ese recordatorio no se manda:
    quien reserva dos horas antes acaba de ver la cita y no necesita el aviso de 24 h.
    """
    restante = reserva.inicio_utc - ahora
    antelacion_al_crear = reserva.inicio_utc - reserva.fecha_creacion
    pendientes = []
    for n, horas in horas_de_recordatorio(reserva):
        ventana = timedelta(hours=horas)
        if (
            restante <= ventana
            and antelacion_al_crear > ventana
            and not getattr(reserva, f'sms_recordatorio_{n}_procesado')
            and getattr(reserva, f'sms_recordatorio_{n}_intentos') < MAX_INTENTOS
        ):
            pendientes.append((n, horas))
    return sorted(pendientes, key=lambda par: par[1])


def _enviar_recordatorio(reserva, n):
    from .models import LogSMS

    telefono = normalizar_telefono(reserva.telefono_invitado)
    mensaje = mensaje_de_reserva(reserva)
    if telefono:
        resultado = enviar_sms(telefono, mensaje)
    else:
        resultado = ResultadoEnvio(False, error=f'Teléfono no válido: {reserva.telefono_invitado}')

    LogSMS.objects.create(
        reserva=reserva,
        tipo=f'recordatorio_{n}',
        telefono=telefono or reserva.telefono_invitado[:50],
        mensaje=mensaje,
        exitoso=resultado.ok,
        id_proveedor=resultado.id_proveedor,
        error_detalle=resultado.error,
        respuesta=resultado.respuesta,
    )
    return resultado


def procesar_recordatorios(ahora=None, limite=MAX_POR_EJECUCION):
    """Envía los SMS que tocan. Devuelve (enviados, errores, quedan_pendientes)."""
    from .models import Reserva

    ahora = ahora or datetime.now(timezone.utc)
    reservas = (
        Reserva.objects
        .filter(
            event_type__sms_activo=True,
            estado=Reserva.Estado.CONFIRMADA,
            inicio_utc__gt=ahora,
        )
        .filter(Q(sms_recordatorio_1_procesado=False) | Q(sms_recordatorio_2_procesado=False))
        .exclude(telefono_invitado='')
        .select_related('event_type', 'host')
        .order_by('inicio_utc')
    )

    enviados = errores = 0
    for reserva in reservas:
        pendientes = _pendientes_ahora(reserva, ahora)
        if not pendientes:
            continue
        if limite and enviados + errores >= limite:
            return enviados, errores, True

        # Si se acumulan varios (el cron estuvo parado), solo sale el más cercano
        # a la cita: el resto ya llega tarde y se da por pasado sin gastar un SMS.
        (n, _), *atrasados = pendientes
        for atrasado, _ in atrasados:
            _reclamar(reserva, atrasado)
        if not _reclamar(reserva, n):
            continue

        resultado = _enviar_recordatorio(reserva, n)
        if resultado.ok:
            enviados += 1
            continue

        errores += 1
        logger.error('SMS no enviado para la reserva %s: %s', reserva.pk, resultado.error)
        if resultado.detener_pasada:
            # Sin saldo o sin credenciales fallarían todos. No se gastan intentos:
            # en cuanto se arregle la cuenta, los que sigan a tiempo saldrán.
            _devolver(reserva, n, sumar_intento=False)
            return enviados, errores, True
        if resultado.reintentable:
            _devolver(reserva, n, sumar_intento=True)
    return enviados, errores, False
