"""Orquestación del espejo Bunny → R2.

Por cada vídeo se copian tres objetos, siempre con los mismos nombres:

    {library_id}/{guid}/video.mp4       el mejor MP4 que Bunny tenga
    {library_id}/{guid}/thumbnail.jpg   la miniatura activa, no las candidatas
    {library_id}/{guid}/meta.json       título, duración, resolución, colección

Que el vídeo se llame siempre `video.mp4` es lo que hace la ruta predecible: el
LMS y los funnels ya guardan library_id y guid, así que pueden componer la URL
sin consultar nada ni saber si esa clase acabó en 720p o en 1080p.
"""

import logging

from django.utils import timezone

from ..models import VideoEspejo
from . import bunny, r2

logger = logging.getLogger(__name__)

# Las miniaturas candidatas que genera Bunny (thumbnail_1..5.jpg) no interesan:
# la buena es la que dice `thumbnailFileName`, que es la que alguien eligió.
NOMBRE_VIDEO = 'video.mp4'
NOMBRE_THUMB = 'thumbnail.jpg'
NOMBRE_META = 'meta.json'


def _necesita_copia(fila, video):
    """True si hay que copiar: nunca se copió, falló, o el vídeo cambió en Bunny."""
    if fila.estado in (VideoEspejo.PENDIENTE, VideoEspejo.FALLIDO):
        return True
    if fila.estado == VideoEspejo.OMITIDO:
        # Se omitió por algo permanente (sin MP4, sin terminar). Sólo se
        # reintenta si el vídeo ha cambiado de tamaño desde entonces.
        return (video.get('storageSize') or 0) != fila.bytes_origen
    return (video.get('storageSize') or 0) != fila.bytes_origen


def _ya_esta_en_r2(library_id, guid, bytes_esperados):
    """True si el MP4 ya está en R2 con el tamaño que toca.

    La tabla dice lo que copió ESTA base de datos, y el bucket es uno solo para
    todas: la carga inicial puede lanzarse desde un portátil y el goteo diario
    correr en producción. Sin esta comprobación, el primer barrido de
    producción volvería a subir el catálogo entero (que ya está ahí) sólo
    porque su tabla está vacía. Un HEAD por vídeo cuesta una operación clase B
    —$0,36 por millón— y evita repetir teras.
    """
    if not bytes_esperados:
        return False
    key = f'{library_id}/{guid}/{NOMBRE_VIDEO}'
    return r2.tamano_objeto(key) == bytes_esperados


def copiar_video(libreria, credenciales, video):
    """Copia un vídeo a R2 y devuelve su fila actualizada.

    `libreria` es el dict de la API de cuenta y `credenciales` la tripleta
    (hostname, zona, password) de su storage zone, que el llamador resuelve una
    vez por librería en vez de por vídeo.
    """
    hostname, zona, password = credenciales
    guid = video['guid']
    library_id = str(libreria['Id'])

    fila, _ = VideoEspejo.objects.get_or_create(
        library_id=library_id,
        guid=guid,
        defaults={'library_nombre': libreria.get('Name', '')},
    )
    fila.library_nombre = libreria.get('Name', '')
    fila.titulo = (video.get('title') or '')[:500]
    fila.duracion_segundos = video.get('length') or 0
    fila.bytes_origen = video.get('storageSize') or 0
    fila.intentos += 1

    if video.get('status') != bunny.STATUS_TERMINADO:
        fila.estado = VideoEspejo.OMITIDO
        fila.ultimo_error = f'El vídeo no ha terminado de transcodificar (status={video.get("status")})'
        fila.save()
        return fila

    try:
        ficheros = bunny.listar_ficheros(hostname, zona, password, guid)
        elegido = bunny.elegir_mp4(ficheros)
        if not elegido:
            fila.estado = VideoEspejo.OMITIDO
            fila.ultimo_error = 'La carpeta no tiene ningún play_*.mp4'
            fila.save()
            return fila

        nombre_mp4, resolucion, bytes_mp4 = elegido
        prefijo = f'{library_id}/{guid}'
        ya_estaba = _ya_esta_en_r2(library_id, guid, bytes_mp4)

        if not ya_estaba:
            with bunny.abrir_fichero(hostname, zona, password, guid, nombre_mp4) as resp:
                resp.raw.decode_content = True
                r2.subir_stream(resp.raw, f'{prefijo}/{NOMBRE_VIDEO}', 'video/mp4')

        thumb = video.get('thumbnailFileName') or 'thumbnail.jpg'
        if ficheros.get(thumb) and not ya_estaba:
            with bunny.abrir_fichero(hostname, zona, password, guid, thumb) as resp:
                resp.raw.decode_content = True
                r2.subir_stream(resp.raw, f'{prefijo}/{NOMBRE_THUMB}', 'image/jpeg')

        r2.subir_json({
            'guid': guid,
            'library_id': library_id,
            'library': libreria.get('Name', ''),
            'title': video.get('title'),
            'length_seconds': video.get('length'),
            'width': video.get('width'),
            'height': video.get('height'),
            'resolucion_copiada': resolucion,
            'available_resolutions': video.get('availableResolutions'),
            'thumbnail_original': thumb,
            'collection_id': video.get('collectionId'),
            'date_uploaded': video.get('dateUploaded'),
            'storage_size_bunny': video.get('storageSize'),
            'copiado_en': timezone.now().isoformat(),
        }, f'{prefijo}/{NOMBRE_META}')

    except Exception as exc:  # noqa: BLE001 — cualquier fallo deja la fila reintentable
        fila.estado = VideoEspejo.FALLIDO
        fila.ultimo_error = str(exc)[:1000]
        fila.save()
        logger.warning('video_backup: falló %s/%s: %s', library_id, guid, exc)
        return fila

    fila.resolucion = resolucion
    fila.bytes_copiados = bytes_mp4
    fila.r2_key = f'{prefijo}/{NOMBRE_VIDEO}'
    fila.estado = VideoEspejo.COPIADO
    fila.ultimo_error = ''
    fila.copiado_en = timezone.now()
    fila.borrado_en_bunny = None
    fila.save()
    # Marca efímera (no se persiste): sólo para que el barrido pueda decir en
    # pantalla si el objeto hubo que subirlo o ya estaba en el bucket.
    fila.ya_estaba_en_r2 = ya_estaba
    return fila


def barrer(limite=None, library_id=None, dry_run=False, log=None):
    """Recorre Bunny y copia lo que falte. Devuelve un resumen del barrido.

    Es el único disparador del espejo: no usamos el webhook de Bunny porque cada
    librería admite una sola URL y el LMS ya la tiene ocupada para marcar sus
    vídeos como listos. Un barrido además ve las librerías enteras, incluidos
    los vídeos que alguien sube directamente al panel de Bunny, que ningún
    webhook nuestro vería.
    """
    escribir = log or (lambda *_: None)
    resumen = {'revisados': 0, 'copiados': 0, 'ya_estaban': 0, 'fallidos': 0,
               'omitidos': 0, 'pendientes': 0}

    librerias = bunny.listar_librerias()
    if library_id:
        librerias = [lib for lib in librerias if str(lib['Id']) == str(library_id)]

    for libreria in librerias:
        lid = str(libreria['Id'])
        try:
            credenciales = bunny.credenciales_storage(libreria)
        except Exception as exc:  # noqa: BLE001
            escribir(f'  {libreria.get("Name")}: no se pudo leer la storage zone ({exc})')
            continue

        existentes = {
            fila.guid: fila
            for fila in VideoEspejo.objects.filter(library_id=lid)
        }
        vistos = set()
        escribir(f'· {libreria.get("Name")} ({lid})')

        for video in bunny.listar_videos(lid, libreria['ApiKey']):
            resumen['revisados'] += 1
            guid = video['guid']
            vistos.add(guid)
            fila = existentes.get(guid)

            if fila and not _necesita_copia(fila, video):
                continue

            if limite is not None and resumen['copiados'] + resumen['fallidos'] >= limite:
                resumen['pendientes'] += 1
                continue

            if dry_run:
                resumen['pendientes'] += 1
                escribir(f'    [dry-run] copiaría {guid} — {(video.get("title") or "")[:50]}')
                continue

            actualizada = copiar_video(libreria, credenciales, video)
            if actualizada.estado == VideoEspejo.COPIADO:
                if getattr(actualizada, 'ya_estaba_en_r2', False):
                    resumen['ya_estaban'] += 1
                    escribir(f'    = {guid} ya estaba en R2, sólo se registró')
                else:
                    resumen['copiados'] += 1
                    escribir(f'    ✓ {guid} {actualizada.resolucion} {actualizada.bytes_copiados / 1e6:.0f} MB')
            elif actualizada.estado == VideoEspejo.OMITIDO:
                resumen['omitidos'] += 1
                escribir(f'    – {guid} omitido: {actualizada.ultimo_error}')
            else:
                resumen['fallidos'] += 1
                escribir(f'    ✗ {guid}: {actualizada.ultimo_error[:120]}')

        # Lo que ya no está en Bunny se marca, pero la copia se queda: si alguien
        # borra un vídeo por error, el respaldo es exactamente lo que lo salva.
        desaparecidos = [
            fila for guid, fila in existentes.items()
            if guid not in vistos and fila.borrado_en_bunny is None
        ]
        for fila in desaparecidos:
            fila.borrado_en_bunny = timezone.now()
            fila.save(update_fields=['borrado_en_bunny', 'actualizado'])
        if desaparecidos:
            escribir(f'    {len(desaparecidos)} vídeo(s) ya no están en Bunny (la copia se conserva)')

    return resumen
