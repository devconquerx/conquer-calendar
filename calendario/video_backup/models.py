from django.db import models


class VideoEspejo(models.Model):
    """Un vídeo de Bunny Stream copiado (o por copiar) a Cloudflare R2.

    La tabla es el registro del respaldo, no del uso: aquí entra todo lo que
    hay en la cuenta de Bunny, esté o no pegado en una clase del LMS o en un
    funnel. Un vídeo recién subido que nadie ha enlazado todavía también se
    respalda, porque el día que Bunny caiga nadie va a preguntarse si la clase
    ya estaba publicada.

    La clave real es (library_id, guid): es la que compone la ruta en R2 y la
    que aparece en las URLs que guardan el LMS y los funnels.
    """

    PENDIENTE = 'pendiente'
    COPIADO = 'copiado'
    FALLIDO = 'fallido'
    OMITIDO = 'omitido'

    ESTADOS = [
        (PENDIENTE, 'Pendiente'),
        (COPIADO, 'Copiado'),
        (FALLIDO, 'Fallido'),
        (OMITIDO, 'Omitido'),
    ]

    library_id = models.CharField(max_length=20, db_index=True)
    library_nombre = models.CharField(max_length=200, blank=True, default='')
    guid = models.CharField(max_length=36, db_index=True)

    titulo = models.CharField(max_length=500, blank=True, default='')
    duracion_segundos = models.PositiveIntegerField(default=0)
    # Resolución que se acabó copiando: la mejor que Bunny tenga como MP4, que
    # no siempre es la mejor que anuncia (el 1080p a veces existe sólo en HLS).
    resolucion = models.CharField(max_length=10, blank=True, default='')

    # Tamaño del MP4 copiado, y tamaño total del vídeo en Bunny (todas las
    # resoluciones). El segundo es el que delata que el vídeo se ha resubido
    # con el mismo GUID y hay que volver a copiarlo.
    bytes_copiados = models.BigIntegerField(default=0)
    bytes_origen = models.BigIntegerField(default=0)

    r2_key = models.CharField(max_length=300, blank=True, default='')
    estado = models.CharField(max_length=12, choices=ESTADOS, default=PENDIENTE, db_index=True)
    intentos = models.PositiveIntegerField(default=0)
    ultimo_error = models.TextField(blank=True, default='')

    copiado_en = models.DateTimeField(null=True, blank=True)
    # Se marca cuando el GUID deja de aparecer en Bunny. La copia NO se borra:
    # esto es un respaldo, y un borrado por error en Bunny es justo uno de los
    # casos de los que protege.
    borrado_en_bunny = models.DateTimeField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'video_backup_espejo'
        ordering = ['-creado']
        constraints = [
            models.UniqueConstraint(fields=['library_id', 'guid'], name='uniq_libreria_guid'),
        ]

    def __str__(self):
        return f'{self.library_id}/{self.guid} [{self.estado}]'

    @property
    def prefijo_r2(self):
        return f'{self.library_id}/{self.guid}'
