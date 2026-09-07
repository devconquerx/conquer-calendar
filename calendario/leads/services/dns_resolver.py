"""
Resolución de registros MX sin dependencias externas.

La imagen de Django no trae dnspython ni utilidades del sistema (dig, nslookup,
host), y añadirlas obligaría a reconstruir la imagen. Como lo único que hace
falta es una consulta MX puntual por dominio, aquí va un cliente DNS mínimo
sobre UDP que construye y parsea el paquete a mano.
"""

import ipaddress
import os
import random
import socket
import struct
import threading

DNS_PORT = 53
TYPE_MX = 15
TYPE_A = 1
TYPE_CNAME = 5
CLASS_IN = 1

DEFAULT_NAMESERVERS = ['8.8.8.8', '1.1.1.1']

# Cache de MX por dominio compartida en el proceso: un lote de verificación
# repite muchísimo los mismos dominios (gmail.com es el 84% del volumen).
_mx_cache = {}
_mx_cache_lock = threading.Lock()


def get_system_nameservers():
    """Lee los resolvers de /etc/resolv.conf, con fallback a resolvers públicos."""
    servers = []
    try:
        with open('/etc/resolv.conf', 'r') as fh:
            for line in fh:
                line = line.strip()
                if line.startswith('nameserver'):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
    except OSError:
        pass
    return servers or DEFAULT_NAMESERVERS


def _encode_name(name):
    """Codifica 'gmail.com' como \\x05gmail\\x03com\\x00."""
    out = b''
    for label in name.rstrip('.').split('.'):
        label_bytes = label.encode('idna') if any(ord(c) > 127 for c in label) else label.encode('ascii')
        if len(label_bytes) > 63:
            raise ValueError(f"Label DNS demasiado largo: {label}")
        out += bytes([len(label_bytes)]) + label_bytes
    return out + b'\x00'


def _decode_name(data, offset):
    """
    Decodifica un nombre DNS soportando punteros de compresión (0xC0).

    Devuelve (nombre, offset_siguiente). El offset devuelto es el que sigue al
    nombre en la posición original, no el destino del puntero.
    """
    labels = []
    jumped = False
    next_offset = offset
    hops = 0

    while True:
        if offset >= len(data):
            break
        length = data[offset]

        # Puntero de compresión: los dos bits altos a 1
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                break
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                next_offset = offset + 2
                jumped = True
            offset = pointer
            hops += 1
            if hops > 20:  # bucle de punteros malicioso o corrupto
                break
            continue

        if length == 0:
            if not jumped:
                next_offset = offset + 1
            break

        offset += 1
        labels.append(data[offset:offset + length].decode('ascii', errors='replace'))
        offset += length
        if not jumped:
            next_offset = offset

    return '.'.join(labels), next_offset


def _build_query(domain, query_id, qtype=TYPE_MX):
    header = struct.pack('!HHHHHH', query_id, 0x0100, 1, 0, 0, 0)
    question = _encode_name(domain) + struct.pack('!HH', qtype, CLASS_IN)
    return header + question


def _parse_response(data, query_id, qtype=TYPE_MX):
    """
    Devuelve los registros del tipo pedido.

    Para MX, una lista de (preferencia, host). Para A, una lista de (0, ip).
    """
    if len(data) < 12:
        return []

    resp_id, flags, qdcount, ancount, _nscount, _arcount = struct.unpack('!HHHHHH', data[:12])
    if resp_id != query_id:
        return []

    rcode = flags & 0x000F
    if rcode != 0:  # NXDOMAIN (3) u otro error: el dominio no acepta correo
        return []

    offset = 12
    for _ in range(qdcount):
        _name, offset = _decode_name(data, offset)
        offset += 4  # QTYPE + QCLASS

    records = []
    for _ in range(ancount):
        if offset >= len(data):
            break
        _name, offset = _decode_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, _rclass, _ttl, rdlength = struct.unpack('!HHIH', data[offset:offset + 10])
        offset += 10
        rdata_end = offset + rdlength

        if qtype == TYPE_MX and rtype == TYPE_MX and rdlength >= 3:
            preference = struct.unpack('!H', data[offset:offset + 2])[0]
            host, _ = _decode_name(data, offset + 2)
            if host:
                records.append((preference, host))
        elif qtype == TYPE_A and rtype == TYPE_A and rdlength == 4:
            ip = '.'.join(str(b) for b in data[offset:offset + 4])
            records.append((0, ip))
        elif rtype == TYPE_CNAME:
            pass  # un CNAME no aporta por sí mismo destino de correo

        offset = rdata_end

    return records


def _es_ip_publica(ip):
    """
    Descarta IPs que no pueden ser un servidor de correo real.

    Protege del secuestro de NXDOMAIN y del DNS wildcard de dominios
    aparcados, que devuelven direcciones privadas o reservadas para dominios
    que en realidad no existen. Sin esto, el fallback al registro A daría por
    bueno cualquier dominio.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified)


def _query(domain, qtype, timeout):
    """Lanza la consulta contra los resolvers del sistema. None = no se pudo."""
    for server in get_system_nameservers():
        query_id = random.randint(0, 0xFFFF)
        try:
            query = _build_query(domain, query_id, qtype)
        except (ValueError, UnicodeError):
            return []

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(query, (server, DNS_PORT))
            data, _addr = sock.recvfrom(4096)
            records = _parse_response(data, query_id, qtype)
            return [valor for _pref, valor in sorted(records, key=lambda r: r[0])]
        except (socket.timeout, OSError):
            continue
        finally:
            sock.close()
    return None


def resolve_mx(domain, timeout=5.0, use_cache=True):
    """
    Devuelve los hosts a los que entregar correo del dominio, por preferencia.

    Si el dominio no publica MX se cae al registro A: por RFC 5321 §5.1 ese
    host actúa como MX implícito, y tratarlo como "no recibe correo" marcaría
    inválidos dominios legítimos.

    Lista vacía = el dominio no puede recibir correo. None = la consulta falló
    (red/timeout), que es distinto y no debe bloquear ningún lead.
    """
    domain = (domain or '').strip().lower().rstrip('.')
    if not domain:
        return []

    if use_cache:
        with _mx_cache_lock:
            if domain in _mx_cache:
                return _mx_cache[domain]

    result = _query(domain, TYPE_MX, timeout)

    if result == []:
        # Sin MX: probar el A como MX implícito antes de darlo por muerto
        a_records = _query(domain, TYPE_A, timeout)
        if a_records is None:
            result = None
        elif any(_es_ip_publica(ip) for ip in a_records):
            result = [domain]

    if use_cache and result is not None:
        with _mx_cache_lock:
            _mx_cache[domain] = result

    return result


def clear_cache():
    with _mx_cache_lock:
        _mx_cache.clear()
