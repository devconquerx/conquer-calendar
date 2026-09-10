"""Subida a Cloudflare R2 (S3 compatible).

Se sube en streaming: lo que llega de la Storage API de Bunny va directo a R2 en
partes de 16 MB, sin escribirse en disco. Un vídeo de 1 GB no ocupa más de una
parte en memoria.
"""

import json
import logging

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from django.conf import settings

logger = logging.getLogger(__name__)

TAMANO_PARTE = 16 * 1024 * 1024

# 4 hilos por vídeo es suficiente: el cuello de botella es la lectura desde
# Bunny, no la escritura en R2.
TRANSFERENCIA = TransferConfig(
    multipart_threshold=TAMANO_PARTE,
    multipart_chunksize=TAMANO_PARTE,
    max_concurrency=4,
    use_threads=True,
)


class R2Error(Exception):
    pass


def _cliente():
    if not settings.R2_ENDPOINT or not settings.R2_ACCESS_KEY_ID:
        raise R2Error('Faltan credenciales de R2 (R2_ENDPOINT / R2_ACCESS_KEY_ID)')
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name='auto',
        config=Config(retries={'max_attempts': 5, 'mode': 'standard'}),
    )


def subir_stream(fileobj, key, content_type):
    """Vuelca un file-like a R2. Devuelve la key escrita."""
    _cliente().upload_fileobj(
        fileobj,
        settings.R2_BUCKET,
        key,
        ExtraArgs={'ContentType': content_type},
        Config=TRANSFERENCIA,
    )
    return key


def subir_bytes(datos, key, content_type):
    _cliente().put_object(
        Bucket=settings.R2_BUCKET,
        Key=key,
        Body=datos,
        ContentType=content_type,
    )
    return key


def subir_json(datos, key):
    return subir_bytes(
        json.dumps(datos, ensure_ascii=False, indent=1).encode('utf-8'),
        key,
        'application/json',
    )


def tamano_objeto(key):
    """Bytes del objeto en R2, o None si no está. Sirve para verificar sin descargar."""
    try:
        return _cliente().head_object(Bucket=settings.R2_BUCKET, Key=key)['ContentLength']
    except Exception:
        return None
