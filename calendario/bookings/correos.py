from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.templatetags.static import static
from django.template.loader import render_to_string


_DIAS_ABREV  = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
_MESES_ABREV = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def _fmt_fecha(inicio_dt, duracion_min):
    fin_dt   = inicio_dt + timedelta(minutes=duracion_min)
    dia      = _DIAS_ABREV[inicio_dt.weekday()]
    mes      = _MESES_ABREV[inicio_dt.month - 1]
    hora_fin = (
        str(fin_dt.hour) if fin_dt.minute == 0
        else f"{fin_dt.hour}:{fin_dt.minute:02d}"
    )
    return (
        f"{dia} {inicio_dt.day} de {mes} {inicio_dt.year} "
        f"· {inicio_dt.hour}:{inicio_dt.minute:02d} – {hora_fin}"
    )


def resolver_config(reserva, tipo_correo):
    """
    Devuelve (plantilla, config) o (None, None).
    tipo_correo: 'confirmacion_host' | 'confirmacion_inv' | 'recordatorio'
    Jerarquía: EventType → Grupo del host → Config global → None
    """
    # 1. Config explícita del EventType
    try:
        config = reserva.event_type.config_correo
        plantilla = getattr(config, f'plantilla_{tipo_correo}', None)
        if plantilla and plantilla.activa:
            return plantilla, config
    except Exception:
        pass

    # 2. Config por miembro dentro del grupo
    try:
        from .models import ConfigCorreoMiembroGrupo
        for membresia in reserva.host.membresias_grupo.all():
            try:
                cfg_miembro = ConfigCorreoMiembroGrupo.objects.get(
                    grupo=membresia.grupo, usuario=reserva.host
                )
                plantilla = getattr(cfg_miembro, f'plantilla_{tipo_correo}', None)
                if plantilla and plantilla.activa:
                    return plantilla, cfg_miembro
            except ConfigCorreoMiembroGrupo.DoesNotExist:
                continue
    except Exception:
        pass

    # 3. Config del grupo del host
    try:
        for membresia in reserva.host.membresias_grupo.select_related('grupo__config_correo').all():
            try:
                config_grupo = membresia.grupo.config_correo
                plantilla = getattr(config_grupo, f'plantilla_{tipo_correo}', None)
                if plantilla and plantilla.activa:
                    return plantilla, config_grupo
            except Exception:
                continue
    except Exception:
        pass

    # 4. Config global por defecto
    try:
        from .models import ConfigCorreoDefault
        config_default = ConfigCorreoDefault.get()
        plantilla = getattr(config_default, f'plantilla_{tipo_correo}', None)
        if plantilla and plantilla.activa:
            return plantilla, config_default
    except Exception:
        pass

    return None, None


def _build_vars(reserva, site_url):
    duracion_min = reserva.event_type.duracion_minutos

    # Timezone del invitado
    tz_inv_str = reserva.timezone_invitado or reserva.host.timezone
    try:
        tz_inv = ZoneInfo(tz_inv_str)
    except Exception:
        tz_inv = ZoneInfo('UTC')
    inicio_inv = reserva.inicio_utc.astimezone(tz_inv)
    fecha_hora_invitado = _fmt_fecha(inicio_inv, duracion_min)

    # Timezone del host
    tz_host_str = reserva.host.timezone
    try:
        tz_host = ZoneInfo(tz_host_str)
    except Exception:
        tz_host = ZoneInfo('UTC')
    inicio_host = reserva.inicio_utc.astimezone(tz_host)
    fecha_hora_host = _fmt_fecha(inicio_host, duracion_min)

    # UTC
    utc = reserva.inicio_utc
    fecha_hora_utc = f"{utc.hour}:{utc.minute:02d} UTC"

    return {
        'nombre_invitado':    reserva.nombre_invitado,
        'email_invitado':     reserva.email_invitado,
        'telefono_invitado':  reserva.telefono_invitado or '',
        'nombre_host':        reserva.host.get_full_name() or reserva.host.username,
        'email_host':         reserva.host.email,
        'nombre_evento':      reserva.event_type.nombre,
        'fecha_hora':         fecha_hora_invitado,   # alias backwards compat
        'fecha_hora_invitado': fecha_hora_invitado,
        'fecha_hora_host':    fecha_hora_host,
        'fecha_hora_utc':     fecha_hora_utc,
        'timezone':           tz_inv_str,
        'timezone_host':      tz_host_str,
        'duracion':           str(duracion_min),
        'google_meet_url':    reserva.google_meet_url or '',
        'google_event_url':   reserva.google_event_url or '',
        'link_cancelar':      f"{site_url}/r/{reserva.confirmacion_token}/cancelar/",
        'link_reserva':       f"{site_url}/panel/reservas/{reserva.pk}/",
    }


def _render_variables(texto, vars_dict):
    for key, valor in vars_dict.items():
        texto = texto.replace('{{' + key + '}}', valor)
    return texto


def _logo_url(plantilla):
    if not plantilla.logo:
        return None
    try:
        url = plantilla.logo.url
        site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
        if url.startswith('/'):
            return f"{site_url}{url}"
        return url
    except Exception:
        return None


def _enviar(reserva, tipo_correo, destinatario, plantilla):
    from .models import LogCorreo

    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    vars_dict = _build_vars(reserva, site_url)

    asunto       = _render_variables(plantilla.texto_encabezado, vars_dict)
    cuerpo_texto = _render_variables(plantilla.cuerpo, vars_dict)
    campos       = set(v.strip('{}') for v in (plantilla.campos_visibles or []))

    # Logo público — en producción usar SITE_URL del servidor real
    static_logo = f"{site_url}{static('correos/conquerx-logo.png')}"
    default_logo_url = (
        static_logo if not site_url.startswith('http://localhost')
        else 'https://krctool.s3.eu-west-3.amazonaws.com/logo_conquercrm_email.png'
    )

    html_content = render_to_string('correos/base.html', {
        'logo_url':         _logo_url(plantilla),
        'default_logo_url': default_logo_url,
        'color_encabezado': plantilla.color_encabezado or '#111827',
        'texto_encabezado': asunto,
        'cuerpo':           cuerpo_texto,
        'pie_pagina':       plantilla.pie_pagina,
        'campos':           campos,
        **vars_dict,
    })

    exitoso = False
    error_detalle = ''
    try:
        send_mail(
            subject=asunto,
            message=cuerpo_texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            html_message=html_content,
            fail_silently=False,
        )
        exitoso = True
    except Exception as exc:
        error_detalle = str(exc)

    LogCorreo.objects.create(
        reserva=reserva,
        tipo=tipo_correo,
        plantilla=plantilla,
        destinatario=destinatario,
        exitoso=exitoso,
        error_detalle=error_detalle,
        html_content=html_content,
        payload=vars_dict,
    )

    return exitoso


def enviar_confirmacion_host(reserva):
    plantilla, _ = resolver_config(reserva, 'confirmacion_host')
    if not plantilla:
        return
    _enviar(reserva, 'confirmacion_host', reserva.host.email, plantilla)


def enviar_confirmacion_invitado(reserva):
    plantilla, _ = resolver_config(reserva, 'confirmacion_inv')
    if not plantilla:
        return
    _enviar(reserva, 'confirmacion_inv', reserva.email_invitado, plantilla)
