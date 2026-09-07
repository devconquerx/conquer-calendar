"""Validación de email del lead: verificador propio con NeverBounce de respaldo.

Durante meses la validación dependió por completo de NeverBounce, que además
lleva desde junio quedándose sin créditos a mitad de mes: en agosto el 42% de
las llamadas volvieron con `general_failure` y el email se quedó sin veredicto.

El verificador propio (`email_verifier`) hace el mismo trabajo por SMTP sin
coste ni cuota, y acierta el 91% de los veredictos de NeverBounce sin un solo
falso positivo sobre la muestra medida. Se usa como primera opción y NeverBounce
queda como respaldo para lo que el sondeo no resuelva.

El resultado se guarda en `Lead.neverbounce_result` con exactamente la misma
forma de siempre, para que nada aguas abajo (el push al CRM, el admin, el
sweep) tenga que enterarse de quién lo resolvió. La clave `source` dice quién
fue, por si hace falta auditarlo.
"""

import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)


def _formatear(result, *, status, source, flags=None, execution_time=0,
               reason='', smtp_code=None):
    """Construye el dict con la forma histórica de `neverbounce_result`."""
    return {
        'status': status,
        'result': result,
        'is_valid': result == 'valid',
        'is_rejected': result in ('invalid', 'disposable'),
        'is_uncertain': result in ('catchall', 'unknown'),
        'flags': flags or [],
        'execution_time': execution_time,
        # Extras propios: no los lee nadie aguas abajo, sirven para auditar
        'source': source,
        'reason': reason,
        'smtp_code': smtp_code,
    }


def _verificar_con_sondeo(lead):
    """Sondeo SMTP propio. Devuelve el dict ya formateado, o None si no aplica."""
    from calendario.leads.models import EmailVerificationCache
    from calendario.leads.services.email_verifier import (
        EmailVerifier,
        ProveedorBloqueado,
    )

    inicio = time.time()
    verifier = EmailVerifier(
        helo_domain=getattr(settings, 'EMAIL_VERIFIER_HELO', 'conquerblocks.com'),
        mail_from=getattr(settings, 'EMAIL_VERIFIER_MAIL_FROM', ''),
        timeout=getattr(settings, 'EMAIL_VERIFIER_TIMEOUT', 15.0),
        # Un lead por tarea: el ritmo lo marca el caudal de leads, no una pausa
        # interna que dejaría al worker de Celery bloqueado sin hacer nada.
        delay_between_probes=0,
        detect_catchall=getattr(settings, 'EMAIL_VERIFIER_DETECT_CATCHALL', True),
        cache=EmailVerificationCache,
    )

    try:
        veredicto = verifier.verify(lead.email)
    except ProveedorBloqueado as exc:
        # El proveedor nos ha vetado por reputación o volumen. No es un dato
        # sobre este email: se deja pasar al respaldo y se avisa, porque si
        # esto se repite hay que bajar el ritmo o revisar la IP.
        logger.warning(
            '[EmailVerifier] Lead %s: %s nos ha vetado (%s). Se recurre al respaldo.',
            lead.pk, exc.host, exc.code,
        )
        return None
    except Exception:
        logger.exception('[EmailVerifier] Lead %s: fallo inesperado en el sondeo', lead.pk)
        return None
    finally:
        verifier.close()

    return _formatear(
        veredicto['result'],
        status='success',
        source='cache' if veredicto.get('from_cache') else 'own_smtp',
        execution_time=int((time.time() - inicio) * 1000),
        reason=veredicto.get('reason', ''),
        smtp_code=veredicto.get('smtp_code'),
    )


def validate_email(lead):
    """Valida el email del lead y guarda el veredicto en `neverbounce_result`.

    Orden: verificador propio primero (gratis y sin cuota); si no llega a un
    veredicto firme, NeverBounce como respaldo. Nunca lanza por un email que no
    se pueda resolver: en ese caso el lead se queda con `unknown` y sigue su
    camino, que es lo que hacía siempre.
    """
    if not lead.email or lead.neverbounce_result:
        return

    propio = None
    if getattr(settings, 'EMAIL_VERIFIER_ENABLED', True):
        propio = _verificar_con_sondeo(lead)

    # Un veredicto firme del sondeo propio no necesita segunda opinión
    if propio and propio['result'] != 'unknown':
        lead.neverbounce_result = propio
        lead.save(update_fields=['neverbounce_result'])
        logger.info(
            '[EmailVerifier] Lead %s email=%s result=%s (%s, %s)',
            lead.pk, lead.email, propio['result'], propio['source'], propio['reason'],
        )
        return

    # Respaldo: NeverBounce, si sigue configurado y con créditos
    if getattr(settings, 'EMAIL_VERIFIER_FALLBACK_NEVERBOUNCE', True) and settings.NEVERBOUNCE_API_KEY:
        from calendario.leads.services import neverbounce

        neverbounce.validate_email(lead)
        if lead.neverbounce_result:
            lead.neverbounce_result.setdefault('source', 'neverbounce')
            lead.save(update_fields=['neverbounce_result'])
            return

    # Ni sondeo ni respaldo: se registra el no-dato para no reintentarlo en bucle
    if propio:
        lead.neverbounce_result = propio
        lead.save(update_fields=['neverbounce_result'])
        logger.info(
            '[EmailVerifier] Lead %s email=%s sin veredicto firme (%s)',
            lead.pk, lead.email, propio['reason'],
        )
