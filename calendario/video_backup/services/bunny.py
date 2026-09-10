"""Lectura de la cuenta de Bunny Stream: librerías, vídeos y ficheros crudos.

Hay tres credenciales distintas en juego y confundirlas cuesta un rato de 401s:

  - La API key de cuenta (`BUNNY_ACCOUNT_API_KEY`) sólo vale para api.bunny.net.
  - Cada librería tiene su propia API key, que se lee en `GET /videolibrary/{id}`
    y es la única que acepta video.bunnycdn.com.
  - Cada librería tiene detrás una storage zone con su propia contraseña, que se
    lee en `GET /storagezone/{id}`. Es la que da acceso a los ficheros crudos.

Los ficheros se bajan por la Storage API y no por la pull zone (vz-*.b-cdn.net),
que responde 403 por la protección de hotlink. La Storage API además no factura
tráfico, así que copiar el catálogo entero no cuesta dinero.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_CUENTA = 'https://api.bunny.net'
API_STREAM = 'https://video.bunnycdn.com'

TIMEOUT = 60

# Status 4 = Finished en la API de vídeos (ojo: el enum del webhook es otro).
STATUS_TERMINADO = 4

# De mejor a peor. Bunny no genera MP4 para todas las resoluciones que anuncia
# en `availableResolutions` —el 1080p a veces vive sólo troceado en HLS—, así
# que la resolución buena es la del mejor `play_*.mp4` que exista en disco.
RESOLUCIONES = ['2160p', '1440p', '1080p', '720p', '480p', '360p', '240p']


class BunnyError(Exception):
    pass


def _key_cuenta():
    key = getattr(settings, 'BUNNY_ACCOUNT_API_KEY', '')
    if not key:
        raise BunnyError('Falta BUNNY_ACCOUNT_API_KEY')
    return key


def _get(url, key, params=None, stream=False):
    resp = requests.get(
        url,
        headers={'AccessKey': key, 'accept': 'application/json'},
        params=params,
        timeout=TIMEOUT,
        stream=stream,
    )
    if resp.status_code >= 400:
        raise BunnyError(f'{resp.status_code} en {url.split("?")[0]}: {resp.text[:200]}')
    return resp


def listar_librerias():
    """Todas las librerías de la cuenta, con su API key y su storage zone."""
    resp = _get(f'{API_CUENTA}/videolibrary', _key_cuenta(), params={'page': 1, 'perPage': 100})
    return resp.json().get('Items', [])


def obtener_libreria(library_id):
    return _get(f'{API_CUENTA}/videolibrary/{library_id}', _key_cuenta()).json()


def credenciales_storage(libreria):
    """(hostname, nombre_zona, contraseña_solo_lectura) de la storage zone de una librería."""
    zona = _get(f'{API_CUENTA}/storagezone/{libreria["StorageZoneId"]}', _key_cuenta()).json()
    return zona['StorageHostname'], zona['Name'], zona['ReadOnlyPassword']


def listar_videos(library_id, library_key, por_pagina=100):
    """Itera todos los vídeos de una librería, página a página."""
    pagina = 1
    while True:
        datos = _get(
            f'{API_STREAM}/library/{library_id}/videos',
            library_key,
            params={'page': pagina, 'itemsPerPage': por_pagina},
        ).json()
        items = datos.get('items', [])
        for video in items:
            yield video
        if not items or pagina * por_pagina >= datos.get('totalItems', 0):
            return
        pagina += 1


def listar_ficheros(hostname, zona, password, guid):
    """Ficheros que hay en la carpeta del vídeo, como {nombre: bytes}.

    Sólo el primer nivel: las subcarpetas por resolución son los segmentos .ts
    del HLS —unos 350 por resolución y vídeo— y no se copian. Son el mismo
    contenido que los `play_*.mp4`, troceado.
    """
    resp = _get(f'https://{hostname}/{zona}/{guid}/', password)
    return {
        f['ObjectName']: f.get('Length', 0)
        for f in resp.json()
        if not f.get('IsDirectory')
    }


def elegir_mp4(ficheros):
    """(nombre, resolución, bytes) del mejor MP4 disponible, o None si no hay ninguno."""
    for res in RESOLUCIONES:
        nombre = f'play_{res}.mp4'
        if ficheros.get(nombre):
            return nombre, res, ficheros[nombre]
    return None


def abrir_fichero(hostname, zona, password, guid, nombre):
    """Respuesta en streaming del fichero, para volcarla a R2 sin pasar por disco."""
    return _get(f'https://{hostname}/{zona}/{guid}/{nombre}', password, stream=True)
