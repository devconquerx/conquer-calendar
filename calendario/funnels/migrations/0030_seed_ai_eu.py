# -*- coding: utf-8 -*-
"""Crea el FunnelForm de Conquer AI EU (blocks-ai-eu), clon de Conquer Blocks EU.

Conquer AI es una línea más de Conquer Blocks —vive en su dominio
(www.conquerblocks.com/conquer-ai/...) y comparte píxeles, contenedor de GTM,
cuenta de Google Ads y lista de ActiveCampaign— pero con funnel propio: su
propia landing, su página de vídeo, su StepForm, su calendario y su
confirmación, igual que cb-latam / cb-eu / cb-us son funnels distintos entre sí.
De ahí el reparto de identificadores:

  escuela  conquer-ai      → resuelve las cuatro URLs por el patrón genérico
                             `/conquer-<marca>/...` (ver config/urls.py)
  slug     blocks-ai-eu    → sigue siendo un funnel de Blocks (el tema y los
                             mapeos de marca lo detectan por ahí)
  key      FullAiEu        → el CRM deriva la escuela del prefijo `Full`
                             (ads_source_utils.derive_school_code), así que el
                             prefijo NO es decorativo
  CRM      cb-ai           → una entrada más junto a cb-eu/cb-us/cb-ge; no
                             lleva la región dentro, así que se la declara
                             `FUNNEL_REGION_EXPLICITA` (leads/services/utils.py)

El contenido se copia de la fila VIVA de `FullEu` (Conquer Blocks EU) cuando
existe, no del JSON de `seed_data/`: los seeds son la semilla inicial y llevan
tiempo divergiendo de lo que hay en producción (textos editados desde el admin,
`landing.whatsappOptin`, los `event_type_id` de los tramos de score…). Copiar la
fila viva es lo que hace que esto sea de verdad "una copia de cb-eu". Si no
hubiera `FullEu` (BD fresca), cae al JSON.

Los `score_ranges` se copian tal cual, así que el calendario apunta a los MISMOS
EventTypes que Blocks EU. Es deliberado: el funnel queda reservando desde el
primer día y los EventTypes propios se cambian luego desde el panel.

Idempotente: no toca nada si ya existe la clave (ni pisa ediciones del admin).
"""
import copy
import json
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parents[1] / 'seed_data' / 'ai_eu.json'

KEY = 'FullAiEu'
SLUG = 'blocks-ai-eu'
ESCUELA = 'conquer-ai'
REGION = 'eu'
NOMBRE = 'Conquer AI — EU'

# Funnel del que se clona el contenido: Conquer Blocks EU.
KEY_ORIGEN = 'FullEu'


def _config_del_seed():
    if not SEED_FILE.exists():
        return None
    with SEED_FILE.open(encoding='utf-8') as fh:
        return (json.load(fh) or {}).get('config')


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')

    origen = FunnelForm.objects.filter(key=KEY_ORIGEN).first()
    clon = copy.deepcopy(origen.config) if (origen and origen.config) else None
    semilla = _config_del_seed()
    config = clon or semilla
    if not config:
        return

    # `config['key']` es la réplica del `key` de formObj del funnel viejo: viaja
    # dentro del JSON y hay que reapuntarlo, o el clon se anunciaría como FullEu.
    config['key'] = KEY

    fila = FunnelForm.objects.filter(key=KEY).first()
    if fila is None:
        FunnelForm.objects.create(
            key=KEY, slug=SLUG, escuela=ESCUELA, region=REGION, nombre=NOMBRE,
            config=config,
        )
        return

    # En una BD fresca la fila ya existe al llegar aquí: el glob de 0006 siembra
    # TODOS los JSON de seed_data/, y `ai_eu.json` entra ahí — pero lo hace antes
    # de que a Conquer Blocks EU le lleguen sus parches (0012, 0020, 0025-0027:
    # copia de producción, moneda del objetivo de ingresos, aviso comercial,
    # checkbox de WhatsApp fijo). Ese clon nacería viejo. Como en ese caso su
    # config es literalmente el seed, se distingue de una edición humana y se
    # sustituye por el clon bueno; si alguien lo ha tocado, no se toca.
    if clon and semilla is not None and fila.config == semilla:
        fila.config = config
        fila.save(update_fields=['config'])


def backwards(apps, schema_editor):
    # Al revés SÍ se borra: a diferencia de los seeds compartidos (0006/0021),
    # esta fila la crea únicamente esta migración y no existía antes de ella.
    # Salvo que ya haya recogido prellamadas: `Prellamada.funnel` es PROTECT y
    # revertir una migración no puede llevarse por delante leads reales.
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    funnel = FunnelForm.objects.filter(key=KEY).first()
    if funnel and not funnel.prellamadas.exists():
        funnel.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0029_borrador_de_contenido'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
