from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from calendario.video_backup.models import VideoEspejo
from calendario.video_backup.services import bunny, espejo

LIBRERIA = {'Id': 135359, 'Name': 'Conquer Blocks', 'ApiKey': 'k-libreria', 'StorageZoneId': 299259}
CREDENCIALES = ('storage.bunnycdn.com', 'vz-zona', 'pass-ro')

VIDEO = {
    'guid': 'e123090e-d094-4f85-9662-8ab6cdc7c70c',
    'title': 'Propuesta laboral',
    'length': 307,
    'status': 4,
    'storageSize': 1427892553,
    'width': 1920,
    'height': 1080,
    'availableResolutions': '360p,480p,720p,240p,1080p',
    'thumbnailFileName': 'thumbnail.jpg',
    'collectionId': 'col-1',
    'dateUploaded': '2026-08-17T17:11:24.959',
}

FICHEROS = {
    'original': 997382500,
    'play_1080p.mp4': 93354543,
    'play_720p.mp4': 49483781,
    'play_240p.mp4': 13249984,
    'thumbnail.jpg': 92834,
}


class ElegirMp4Tests(TestCase):
    def test_coge_la_mejor_resolucion_disponible(self):
        self.assertEqual(bunny.elegir_mp4(FICHEROS), ('play_1080p.mp4', '1080p', 93354543))

    def test_baja_un_escalon_si_no_hay_mp4_de_la_mejor(self):
        """Bunny anuncia 1080p aunque a veces sólo exista troceado en HLS."""
        sin_1080 = {k: v for k, v in FICHEROS.items() if k != 'play_1080p.mp4'}
        self.assertEqual(bunny.elegir_mp4(sin_1080), ('play_720p.mp4', '720p', 49483781))

    def test_sin_mp4_devuelve_none(self):
        self.assertIsNone(bunny.elegir_mp4({'original': 1, 'thumbnail.jpg': 2}))


class CopiarVideoTests(TestCase):
    def setUp(self):
        self.parches = [
            patch.object(bunny, 'listar_ficheros', return_value=FICHEROS),
            patch.object(bunny, 'abrir_fichero'),
            patch.object(espejo.r2, 'subir_stream', side_effect=lambda _f, key, _ct: key),
            patch.object(espejo.r2, 'subir_json', side_effect=lambda _d, key: key),
            patch.object(espejo.r2, 'tamano_objeto', return_value=None),
        ]
        for p in self.parches:
            p.start()
            self.addCleanup(p.stop)

    def test_copia_y_deja_la_fila_lista(self):
        fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, VIDEO)

        self.assertEqual(fila.estado, VideoEspejo.COPIADO)
        self.assertEqual(fila.resolucion, '1080p')
        self.assertEqual(fila.bytes_copiados, 93354543)
        self.assertEqual(fila.bytes_origen, VIDEO['storageSize'])
        self.assertEqual(fila.r2_key, f'135359/{VIDEO["guid"]}/video.mp4')
        self.assertIsNotNone(fila.copiado_en)

    def test_un_video_sin_terminar_se_omite_y_no_sube_nada(self):
        with patch.object(espejo.r2, 'subir_stream') as subir:
            fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, {**VIDEO, 'status': 3})

        self.assertEqual(fila.estado, VideoEspejo.OMITIDO)
        subir.assert_not_called()

    def test_un_fallo_de_red_deja_la_fila_reintentable(self):
        with patch.object(bunny, 'listar_ficheros', side_effect=bunny.BunnyError('503')):
            fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, VIDEO)

        self.assertEqual(fila.estado, VideoEspejo.FALLIDO)
        self.assertIn('503', fila.ultimo_error)
        self.assertTrue(espejo._necesita_copia(fila, VIDEO))

    def test_no_se_recopia_lo_que_ya_esta_igual(self):
        fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, VIDEO)
        self.assertFalse(espejo._necesita_copia(fila, VIDEO))

    def test_se_recopia_si_el_video_cambio_en_bunny(self):
        """Mismo GUID con otro tamaño = lo resubieron; la copia está vieja."""
        fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, VIDEO)
        self.assertTrue(espejo._necesita_copia(fila, {**VIDEO, 'storageSize': 999}))

    def test_no_resube_lo_que_ya_esta_en_el_bucket(self):
        """Carga inicial desde un portátil + goteo en producción: dos bases de
        datos distintas, un solo bucket. La tabla vacía de producción no puede
        provocar que se vuelva a subir el catálogo entero."""
        with patch.object(espejo.r2, 'tamano_objeto', return_value=93354543):
            with patch.object(espejo.r2, 'subir_stream') as subir:
                fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, VIDEO)

        subir.assert_not_called()
        self.assertEqual(fila.estado, VideoEspejo.COPIADO)
        self.assertTrue(fila.ya_estaba_en_r2)
        self.assertEqual(fila.r2_key, f'135359/{VIDEO["guid"]}/video.mp4')

    def test_si_el_tamano_en_r2_no_cuadra_se_vuelve_a_subir(self):
        with patch.object(espejo.r2, 'tamano_objeto', return_value=12):
            with patch.object(espejo.r2, 'subir_stream', side_effect=lambda _f, key, _ct: key) as subir:
                fila = espejo.copiar_video(LIBRERIA, CREDENCIALES, VIDEO)

        self.assertTrue(subir.called)
        self.assertFalse(fila.ya_estaba_en_r2)


class BarridoTests(TestCase):
    def setUp(self):
        parches = [
            patch.object(bunny, 'listar_librerias', return_value=[LIBRERIA]),
            patch.object(bunny, 'credenciales_storage', return_value=CREDENCIALES),
            patch.object(bunny, 'listar_videos', return_value=iter([VIDEO])),
            patch.object(bunny, 'listar_ficheros', return_value=FICHEROS),
            patch.object(bunny, 'abrir_fichero'),
            patch.object(espejo.r2, 'subir_stream', side_effect=lambda _f, key, _ct: key),
            patch.object(espejo.r2, 'subir_json', side_effect=lambda _d, key: key),
            patch.object(espejo.r2, 'tamano_objeto', return_value=None),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)

    def test_copia_lo_que_falta(self):
        resumen = espejo.barrer()

        self.assertEqual(resumen['copiados'], 1)
        self.assertEqual(VideoEspejo.objects.filter(estado=VideoEspejo.COPIADO).count(), 1)

    def test_dry_run_no_sube_nada(self):
        with patch.object(espejo.r2, 'subir_stream') as subir:
            resumen = espejo.barrer(dry_run=True)

        subir.assert_not_called()
        self.assertEqual(resumen['pendientes'], 1)
        self.assertEqual(VideoEspejo.objects.count(), 0)

    def test_un_video_que_desaparece_de_bunny_se_marca_pero_no_se_borra(self):
        espejo.barrer()
        with patch.object(bunny, 'listar_videos', return_value=iter([])):
            espejo.barrer()

        fila = VideoEspejo.objects.get(guid=VIDEO['guid'])
        self.assertIsNotNone(fila.borrado_en_bunny)
        self.assertEqual(fila.estado, VideoEspejo.COPIADO)
        self.assertTrue(fila.r2_key)

    def test_el_limite_corta_la_pasada(self):
        otro = {**VIDEO, 'guid': '0' * 8 + '-0000-0000-0000-000000000000'}
        with patch.object(bunny, 'listar_videos', return_value=iter([VIDEO, otro])):
            resumen = espejo.barrer(limite=1)

        self.assertEqual(resumen['copiados'], 1)
        self.assertEqual(resumen['pendientes'], 1)


class ModeloTests(TestCase):
    def test_no_se_pueden_duplicar_guid_en_la_misma_libreria(self):
        from django.db import IntegrityError

        VideoEspejo.objects.create(library_id='1', guid='g', copiado_en=timezone.now())
        with self.assertRaises(IntegrityError):
            VideoEspejo.objects.create(library_id='1', guid='g')

    def test_el_mismo_guid_puede_existir_en_otra_libreria(self):
        VideoEspejo.objects.create(library_id='1', guid='g')
        VideoEspejo.objects.create(library_id='2', guid='g')
        self.assertEqual(VideoEspejo.objects.filter(guid='g').count(), 2)
