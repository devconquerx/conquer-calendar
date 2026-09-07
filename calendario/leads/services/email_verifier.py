"""
Verificación de emails por sondeo SMTP, como alternativa propia a NeverBounce.

Replica lo que hace un verificador comercial: sintaxis -> typos de dominio ->
registros MX -> handshake SMTP truncado (RCPT TO sin DATA, así que nunca se
envía un correo real) -> detección de catch-all.

Filosofía FAIL-OPEN: solo se marca un email como inválido cuando el servidor
responde de forma inequívoca que el buzón no existe. Cualquier duda (timeout,
bloqueo de IP, greylisting, rate limit, catch-all) devuelve un resultado no
concluyente para que el lead se envíe igual. Bloquear un lead bueno cuesta
mucho más que dejar pasar uno malo.
"""

import logging
import random
import re
import smtplib
import socket
import string
import threading
import time
from collections import defaultdict

from .dns_resolver import resolve_mx

logger = logging.getLogger(__name__)


class ProveedorBloqueado(Exception):
    """
    El proveedor ha cortado el acceso a esta IP por volumen o reputación.

    Seguir sondeando cuando aparece esto solo empeora la reputación de la IP,
    así que el lote debe abortar en cuanto se detecta.
    """

    def __init__(self, host, code, message):
        self.host = host
        self.code = code
        self.message = message
        super().__init__(f'{host} respondió {code}: {message[:200]}')

# Mismos valores que devuelve NeverBounce, para poder comparar sin traducir
RESULT_VALID = 'valid'
RESULT_INVALID = 'invalid'
RESULT_CATCHALL = 'catchall'
RESULT_UNKNOWN = 'unknown'

EMAIL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")

# Erratas de dominio detectadas en la propia tabla de LeadRegister más las
# variantes habituales. Un lead con "gmail.con" es basura sin necesidad de
# preguntarle a nadie.
DOMAIN_TYPOS = {
    'gmail.co', 'gmail.con', 'gmail.com.com', 'gmail.cm', 'gmail.om', 'gmail.col',
    'gamil.com', 'gmial.com', 'gmai.com', 'gmaill.com', 'gmail.copm', 'gmail.comm',
    'gnail.com', 'gmail.es.com', 'hotmail.con', 'hotmail.co', 'hotmial.com',
    'hotmai.com', 'hotmail.cm', 'homail.com', 'hotmailcom.com', 'hotmail.com.com',
    'yahoo.con', 'yahoo.co', 'yaho.com', 'yahooo.com',
    'outlok.com', 'outlook.co', 'outloo.com', 'oulook.com',
    'icloud.co', 'iclod.com',
    'example.test', 'example.com', 'test.com', 'test.test',
}

# Códigos de estado extendidos que significan "el buzón de destino no existe"
# (RFC 3463). Es la señal más fiable que existe.
ENHANCED_INVALID = ('5.1.1', '5.1.2', '5.1.3', '5.1.6', '5.1.10')

# Texto típico de "no existe el buzón"
INVALID_PATTERNS = (
    'does not exist', 'doesn\'t exist', 'user unknown', 'unknown user',
    'no such user', 'no such recipient', 'recipient not found', 'user not found',
    'mailbox not found', 'mailbox unavailable', 'no mailbox', 'invalid recipient',
    'recipient rejected', 'recipient address rejected', 'address does not exist',
    'unrouteable address', 'no longer valid', 'account has been disabled',
    'user doesn\'t have', 'not a valid mailbox',
)

# Respuestas que significan "deja de sondear desde esta IP". No son un
# veredicto sobre el email: son un corte del proveedor hacia nosotros.
CORTE_REPUTACION = (
    '4.7.28',                    # Gmail: unusual amount of unsolicited mail
    'unusual amount',
    'unsolicited mail',
    'too many connections',
    'rate limited',
    'try again later',
)

# Distinto del anterior: aquí el proveedor no nos habla por configuración o
# reputación de la IP, y va a responder lo mismo a cada intento. No es urgente
# ni tiene que ver con el ritmo, así que no aborta el lote: se apunta el host
# como mudo y el resto de emails de ese proveedor se resuelven al momento como
# no concluyentes, sin gastar una conexión que ya sabemos cómo acaba.
RECHAZO_PERMANENTE = (
    '5.7.25',                    # Yahoo: forward-confirmed reverse DNS failed
    'reverse dns failed',
    'blocked using',             # Microsoft citando una DNSBL
    "weren't sent",              # Microsoft
    'permanently deferred',      # Yahoo TSS09
)

# Hosts MX que ya sabemos que no nos hablan, compartido por todo el proceso: en
# producción se crea un verificador por lead, así que guardarlo en la instancia
# no serviría de nada y cada email de Hotmail o Yahoo volvería a gastar una
# conexión para recibir el mismo rechazo (entre los dos son el 13% del volumen).
#
# Caduca para que un arreglo de rDNS o una salida de lista negra se detecten
# solos, sin necesidad de reiniciar nada.
_HOSTS_MUDOS = {}                  # host MX -> (motivo, momento en que se apuntó)
_HOSTS_MUDOS_TTL = 3600            # segundos
_hosts_mudos_lock = threading.Lock()


def _marcar_host_mudo(host, motivo):
    with _hosts_mudos_lock:
        _HOSTS_MUDOS[host] = (motivo, time.time())


def _host_esta_mudo(host):
    """Devuelve el motivo si el host nos rechazó hace poco, o None."""
    with _hosts_mudos_lock:
        entrada = _HOSTS_MUDOS.get(host)
        if not entrada:
            return None
        motivo, cuando = entrada
        if time.time() - cuando > _HOSTS_MUDOS_TTL:
            del _HOSTS_MUDOS[host]
            return None
        return motivo

# Texto que indica bloqueo/política/límite: NO es un buzón inexistente. Si esto
# se confundiera con "invalid" se bloquearían leads buenos en masa.
BLOCKED_PATTERNS = (
    'blocked', 'blacklist', 'block list', 'spamhaus', 'barracuda', 'spamcop',
    'policy', 'rate limit', 'too many', 'try again', 'try later', 'greylist',
    'grey list', 'temporarily', 'temporary', 'deferred', 'reputation',
    'not authorized', 'unauthenticated', 'authentication required', 'access denied',
    'service unavailable', 'connection refused', 'too fast', 'throttl',
    'suspicious', 'security', 'unsolicited', 'spam', 'abuse', 'client host',
    'dnsbl', 'rbl', 'sender verify', 'callback', 'refused',
)


class EmailVerifier:
    """
    Verificador SMTP con reutilización de conexión por servidor MX.

    Uso normal (agrupa por dominio automáticamente, mucho más rápido):
        verifier = EmailVerifier()
        for email, res in verifier.verify_many(lista_de_emails):
            ...
        verifier.close()
    """

    def __init__(self, helo_domain='conquerblocks.com', mail_from='',
                 timeout=15.0, delay_between_probes=0.5,
                 max_probes_per_connection=20, detect_catchall=True, cache=None):
        self.helo_domain = helo_domain
        self.mail_from = mail_from
        self.timeout = timeout
        self.delay_between_probes = delay_between_probes
        self.max_probes_per_connection = max_probes_per_connection
        self.detect_catchall = detect_catchall
        # Objeto con get_cached / get_cached_bulk / store. Se inyecta en vez de
        # importarse para que el servicio siga siendo usable sin base de datos.
        self.cache = cache

        self._connections = {}        # host MX -> (smtplib.SMTP, nº de sondeos hechos)
        self._catchall_cache = {}     # dominio -> bool
        self.stats = defaultdict(int)

    # ------------------------------------------------------------------ público

    def verify(self, email, usar_cache=True):
        """Verifica un email y devuelve un dict con el veredicto."""
        if self.cache and usar_cache:
            guardado = self.cache.get_cached(email)
            if guardado:
                self.stats['cache_hit'] += 1
                guardado['duration_ms'] = 0
                return guardado

        started = time.time()
        result = self._verify_inner(email)
        result['duration_ms'] = int((time.time() - started) * 1000)
        result['from_cache'] = False
        self.stats[result['result']] += 1

        if self.cache:
            try:
                self.cache.store(email, result)
            except Exception:
                logger.exception('No se pudo guardar en caché el veredicto de %s', email)

        return result

    def verify_many(self, emails):
        """
        Verifica una lista de emails agrupándolos por dominio.

        Reutiliza la conexión SMTP entre emails del mismo servidor, que es lo
        que hace viable procesar decenas de miles: gmail.com concentra el 84%
        del volumen, así que se abre una conexión y se sondean muchos buzones.
        Devuelve un iterador de (email, resultado).
        """
        emails = list(emails)

        # Un solo golpe a la caché para todo el lote: lo que ya está resuelto
        # no abre conexión SMTP ni gasta reputación.
        en_cache = {}
        if self.cache:
            try:
                en_cache = self.cache.get_cached_bulk(emails)
            except Exception:
                logger.exception('Fallo leyendo la caché en lote; se sondea todo')

        pendientes = []
        for email in emails:
            guardado = en_cache.get((email or '').strip().lower())
            if guardado:
                self.stats['cache_hit'] += 1
                guardado['duration_ms'] = 0
                yield email, guardado
            else:
                pendientes.append(email)

        por_dominio = defaultdict(list)
        sin_dominio = []
        for email in pendientes:
            dominio = self._extract_domain(email)
            if dominio:
                por_dominio[dominio].append(email)
            else:
                sin_dominio.append(email)

        for email in sin_dominio:
            yield email, self.verify(email, usar_cache=False)

        # Los dominios más frecuentes primero: amortizan mejor la conexión
        for dominio in sorted(por_dominio, key=lambda d: -len(por_dominio[d])):
            for email in por_dominio[dominio]:
                yield email, self.verify(email, usar_cache=False)

    def close(self):
        for host, (conn, _count) in list(self._connections.items()):
            try:
                conn.quit()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
        self._connections.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------ interno

    @staticmethod
    def _extract_domain(email):
        if not email or '@' not in email:
            return ''
        return email.strip().lower().rsplit('@', 1)[-1]

    def _build(self, result, reason, smtp_code=None, smtp_message=''):
        return {
            'result': result,
            'is_rejected': result == RESULT_INVALID,
            'reason': reason,
            'smtp_code': smtp_code,
            'smtp_message': (smtp_message or '')[:500],
        }

    def _verify_inner(self, email):
        email = (email or '').strip()

        if not email:
            return self._build(RESULT_INVALID, 'empty')

        # Estructura básica rota: aquí sí se puede afirmar que no es un email
        if email.count('@') != 1 or ' ' in email or '\t' in email:
            return self._build(RESULT_INVALID, 'bad_syntax')

        local, domain = email.rsplit('@', 1)
        domain = domain.lower()

        if (not local or not domain or '.' not in domain or '..' in email
                or domain.startswith('.') or domain.endswith('.')
                or domain.startswith('-') or local.startswith('.') or local.endswith('.')):
            return self._build(RESULT_INVALID, 'bad_syntax')

        # Estructura correcta pero con caracteres fuera del juego habitual: puede
        # ser un email internacionalizado válido (SMTPUTF8), así que no se rechaza.
        if not EMAIL_RE.match(email):
            return self._build(RESULT_UNKNOWN, 'syntax_no_ascii')

        if domain in DOMAIN_TYPOS:
            return self._build(RESULT_INVALID, 'domain_typo')

        mx_hosts = resolve_mx(domain, timeout=self.timeout)
        if mx_hosts is None:
            # Fallo de red/DNS: no sabemos nada, dejar pasar
            return self._build(RESULT_UNKNOWN, 'dns_error')
        if not mx_hosts:
            return self._build(RESULT_INVALID, 'no_mx')

        code, message = self._smtp_probe(mx_hosts, email)
        if code is None:
            return self._build(RESULT_UNKNOWN, 'smtp_unreachable', None, message)

        veredicto, reason = self._classify(code, message)

        # Un 250 solo significa "existe" si el dominio no acepta cualquier cosa
        if veredicto == RESULT_VALID and self.detect_catchall:
            if self._is_catchall(domain, mx_hosts):
                return self._build(RESULT_CATCHALL, 'catchall_domain', code, message)

        return self._build(veredicto, reason, code, message)

    def _classify(self, code, message):
        """Traduce la respuesta SMTP a un veredicto, siempre en modo fail-open."""
        texto = (message or '').lower()

        if code in (250, 251):
            return RESULT_VALID, 'smtp_accepted'

        # 552 = buzón lleno: existe, solo que no cabe más
        if code == 552:
            return RESULT_VALID, 'mailbox_full'

        # 4xx son temporales por definición: nunca son rechazo definitivo
        if 400 <= code < 500:
            return RESULT_UNKNOWN, 'smtp_temporary'

        if 500 <= code < 600:
            # El orden importa: primero descartar que sea un bloqueo hacia
            # nosotros, y solo después mirar si es un buzón inexistente.
            if any(p in texto for p in BLOCKED_PATTERNS):
                return RESULT_UNKNOWN, 'smtp_blocked'
            if any(texto.startswith(e) or f' {e}' in texto for e in ENHANCED_INVALID):
                return RESULT_INVALID, 'smtp_user_unknown'
            if any(p in texto for p in INVALID_PATTERNS):
                return RESULT_INVALID, 'smtp_user_unknown'
            # 5xx sin motivo reconocible: no arriesgarse
            return RESULT_UNKNOWN, 'smtp_5xx_ambiguo'

        return RESULT_UNKNOWN, 'smtp_otro'

    def _is_catchall(self, domain, mx_hosts):
        if domain in self._catchall_cache:
            return self._catchall_cache[domain]

        aleatorio = ''.join(random.choices(string.ascii_lowercase + string.digits, k=18))
        code, _message = self._smtp_probe(mx_hosts, f'{aleatorio}@{domain}')
        # Si acepta un buzón inventado, acepta cualquier cosa
        es_catchall = code in (250, 251)
        self._catchall_cache[domain] = es_catchall
        return es_catchall

    def _get_connection(self, host, forzar_nueva=False):
        """Devuelve una conexión SMTP viva al host, reciclándola si toca."""
        if forzar_nueva:
            entry = self._connections.pop(host, None)
            if entry:
                try:
                    entry[0].close()
                except Exception:
                    pass
            entry = None
        else:
            entry = self._connections.get(host)
        if entry:
            conn, count = entry
            if count < self._max_probes(host):
                try:
                    conn.rset()
                    return conn
                except Exception:
                    pass
            # Agotada o rota: cerrar y abrir otra
            try:
                conn.quit()
            except Exception:
                pass
            self._connections.pop(host, None)

        conn = smtplib.SMTP(timeout=self.timeout)
        code, banner = conn.connect(host, 25)
        texto = banner.decode('utf-8', errors='replace') if isinstance(banner, bytes) else str(banner)
        self._abortar_si_bloqueado(host, code, texto)
        conn.helo(self.helo_domain)
        self._connections[host] = (conn, 0)
        return conn

    def _abortar_si_bloqueado(self, host, code, texto):
        """Corta el lote si el proveedor nos ha vetado, en vez de insistir."""
        bajo = (texto or '').lower()
        if code == 421 or any(f in bajo for f in CORTE_REPUTACION):
            raise ProveedorBloqueado(host, code, texto)
        if any(f in bajo for f in RECHAZO_PERMANENTE):
            if not _host_esta_mudo(host):
                logger.info(
                    'MX %s no acepta sondeos desde esta IP (%s %s): sus emails '
                    'quedarán como no concluyentes durante %s min.',
                    host, code, texto.strip()[:110], _HOSTS_MUDOS_TTL // 60,
                )
            _marcar_host_mudo(host, f'{code} {texto.strip()[:120]}')
            return True
        return False

    def _max_probes(self, host):
        """Outlook y Yahoo cortan sesiones largas; con ellos se recicla antes."""
        host = (host or '').lower()
        if 'outlook' in host or 'yahoodns' in host or 'protection' in host:
            return 1
        return self.max_probes_per_connection

    def _smtp_probe(self, mx_hosts, email):
        """
        Hace MAIL FROM + RCPT TO contra el primer MX que responda.

        Nunca envía DATA, así que el destinatario no recibe nada. Devuelve
        (código, mensaje) o (None, motivo) si no se pudo hablar con ningún MX.

        Cada host se intenta dos veces: Outlook y Yahoo cierran la conexión en
        lugar de responder al RSET cuando se reutiliza la sesión, así que el
        segundo intento fuerza una conexión limpia antes de descartar el host.
        """
        ultimo_error = ''

        candidatos = [h for h in mx_hosts[:3] if not _host_esta_mudo(h)]
        if not candidatos:
            motivo = _host_esta_mudo(mx_hosts[0]) or 'proveedor no sondeable'
            return None, f'MX no sondeable desde esta IP: {motivo}'

        for host in candidatos:
            for intento in (1, 2):
                try:
                    conn = self._get_connection(host, forzar_nueva=(intento == 2))

                    code, msg = conn.docmd('MAIL FROM:', f'<{self.mail_from}>')
                    if code >= 400:
                        texto = msg.decode('utf-8', errors='replace') if isinstance(msg, bytes) else str(msg)
                        # Microsoft y Yahoo rechazan aquí, antes de ver el destinatario:
                        # es un veto a nuestra IP, nunca un veredicto sobre el email.
                        # (lanza si es un corte por volumen; si solo es un
                        # proveedor que no nos habla, lo apunta y sigue)
                        self._abortar_si_bloqueado(host, code, texto)
                        return None, f'MAIL FROM rechazado: {code} {texto[:200]}'

                    code, msg = conn.docmd('RCPT TO:', f'<{email}>')

                    entry = self._connections.get(host)
                    if entry:
                        self._connections[host] = (entry[0], entry[1] + 1)

                    if self.delay_between_probes:
                        time.sleep(self.delay_between_probes)

                    mensaje = msg.decode('utf-8', errors='replace') if isinstance(msg, bytes) else str(msg)
                    return code, mensaje.replace('\n', ' ').strip()

                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                        socket.timeout, socket.error, smtplib.SMTPException, OSError) as exc:
                    ultimo_error = f'{type(exc).__name__}: {exc}'
                    self._connections.pop(host, None)
                    logger.debug('Fallo sondeando %s en %s (intento %s): %s',
                                 email, host, intento, ultimo_error)
                    continue

        return None, ultimo_error


def verify_email(email, **kwargs):
    """Atajo para verificar un único email de forma puntual."""
    with EmailVerifier(**kwargs) as verifier:
        return verifier.verify(email)
